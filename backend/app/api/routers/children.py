from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.db.database import get_db
from backend.app.models.models import (
    Child, User, Parent, Village, Family, ChildVaccination, GrowthRecord, VerificationRecord, AuditLog, LocationVillage
)
from backend.app.schemas.schemas import (
    ChildCreate,
    ChildUpdate,
    ChildSummaryResponse,
    ChildDetailResponse,
    ChildVaccinationResponse
)
from backend.app.services.vaccine_engine import VaccineEngine
from backend.app.services.notification_service import NotificationService
from backend.app.api.deps import get_current_user, require_roles, validate_child_access

router = APIRouter(prefix="/children", tags=["Children"])

@router.post("", response_model=ChildDetailResponse, status_code=status.HTTP_201_CREATED)
def register_child(
    child_in: ChildCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registers a new child in the normalized database and generates complete UIP ChildVaccination schedule.
    """
    # Parent profile determination
    if current_user.role == "parent":
        if not current_user.parent_profile:
            p_profile = Parent(user_id=current_user.id)
            db.add(p_profile)
            db.commit()
            db.refresh(p_profile)
        else:
            p_profile = current_user.parent_profile
        parent_id = p_profile.id
    else:
        # ASHA or Admin registering: find first parent or create parent proxy
        p_profile = db.query(Parent).first()
        parent_id = p_profile.id if p_profile else 1

    village = db.query(Village).filter(Village.id == child_in.village_id).first() if child_in.village_id else None
    if child_in.location_village_id:
        location = db.query(LocationVillage).filter(LocationVillage.id == child_in.location_village_id).first()
        if not location:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected village does not exist.")
        if (child_in.location_taluka_id and location.subdistrict_id != child_in.location_taluka_id) or (
            child_in.location_district_id and location.subdistrict.district_id != child_in.location_district_id
        ) or (
            child_in.location_state_id and location.subdistrict.district.state_id != child_in.location_state_id
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected location hierarchy is inconsistent.")
        village = db.query(Village).filter(Village.location_village_id == location.id).first()
        if not village:
            village = Village(
                name=location.name,
                sub_center=f"{location.subdistrict.name} Sub-Center",
                phc_name=f"{location.subdistrict.district.name} Primary Health Centre",
                district=location.subdistrict.district.name,
                state=location.subdistrict.district.state.name,
                location_village_id=location.id,
            )
            db.add(village)
            db.flush()
    if not village:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid village ID is required for child registration"
        )

    if current_user.role == "parent":
        parent_village_ids = {
            family.village_id for family in p_profile.families
        }
        if village.id not in parent_village_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parents can only register children in their family village."
            )

    # Find or create Family
    family_id = child_in.family_id
    if family_id:
        family = db.query(Family).filter(Family.id == family_id).first()
        family_is_allowed = (
            family is not None
            and family.village_id == village.id
            and (
                current_user.role != "parent"
                or family.parent_id == parent_id
            )
        )
        if not family_is_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The selected family does not belong to the authenticated parent and village."
            )
        if current_user.role != "parent":
            parent_id = family.parent_id
    if not family_id:
        family = db.query(Family).filter(
            Family.parent_id == parent_id,
            Family.village_id == village.id
        ).first()
        if not family:
            family = Family(
                parent_id=parent_id,
                village_id=village.id,
                family_head_name=child_in.father_name or child_in.mother_name or current_user.full_name,
                house_number=child_in.house_number or "1",
                address=f"{child_in.house_number or ''} {village.name}",
                contact_number=child_in.parent_contact or current_user.phone
            )
            db.add(family)
            db.commit()
            db.refresh(family)
        family_id = family.id

    # Generate RCH/MCP Unique ID if not given
    rch_number = child_in.rch_mcp_number
    if not rch_number:
        import uuid
        rch_number = f"RCH-{village.name[:3].upper()}-{date.today().year}-{uuid.uuid4().hex[:6].upper()}"

    new_child = Child(
        family_id=family_id,
        parent_id=parent_id,
        village_id=village.id,
        full_name=child_in.full_name,
        date_of_birth=child_in.date_of_birth,
        gender=child_in.gender,
        birth_weight_kg=child_in.birth_weight_kg,
        blood_group=child_in.blood_group,
        birth_place=child_in.birth_place or "PHC",
        mother_name=child_in.mother_name or (current_user.full_name if current_user.role == "parent" else None),
        father_name=child_in.father_name,
        rch_mcp_number=rch_number,
        house_number=child_in.house_number,
        parent_contact=child_in.parent_contact or current_user.phone,
        registration_date=date.today(),
        verification_status="verified" if current_user.role in ["asha", "admin"] else "pending",
        is_active=True,
        notes=child_in.notes
    )
    db.add(new_child)
    db.commit()
    db.refresh(new_child)

    # Generate ChildVaccination schedule from master VaccinationSchedule
    VaccineEngine.generate_child_schedule(db, new_child)
    db.commit()
    db.refresh(new_child)

    # Birth growth record
    if child_in.birth_weight_kg:
        init_nutritional = "Normal" if child_in.birth_weight_kg >= 2.5 else "MAM - Low Birth Weight"
        birth_growth = GrowthRecord(
            child_id=new_child.id,
            recorded_date=new_child.date_of_birth,
            weight_kg=child_in.birth_weight_kg,
            nutritional_status=init_nutritional,
            notes="Birth weight recorded at registration"
        )
        db.add(birth_growth)
        db.commit()

    # Log audit
    audit = AuditLog(
        user_id=current_user.id,
        action="CHILD_REGISTERED",
        entity_type="Child",
        entity_id=new_child.id,
        details=f"Registered child {new_child.full_name} in village {village.name}"
    )
    db.add(audit)
    db.commit()

    # Trigger Notifications for Parent and Assigned ASHA Worker
    if current_user.role == "parent":
        NotificationService.notify_parent_verification_needed(
            db, current_user.id, new_child.full_name, village.name, new_child.id
        )

    # Notify Village ASHA Worker
    if village.asha_workers:
        for asha_prof in village.asha_workers:
            if asha_prof.user:
                NotificationService.notify_asha_new_registration(
                    db, asha_prof.user.id, new_child.full_name, current_user.full_name, village.name, new_child.id
                )

    return get_child_detail(new_child.id, current_user, db)

@router.get("", response_model=List[ChildSummaryResponse])
def list_children(
    village_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, description="Filter: all, overdue, due, completed, alert"),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists children with role-based filtering:
    - Parent: only their own children
    - ASHA Worker: children in their assigned village
    - Admin: all children
    """
    query = db.query(Child).filter(Child.is_active == True)

    if current_user.role == "parent":
        if current_user.parent_profile:
            query = query.filter(Child.parent_id == current_user.parent_profile.id)
        else:
            return []
    elif current_user.role == "asha":
        if current_user.asha_profile and current_user.asha_profile.assigned_village_id:
            query = query.filter(Child.village_id == current_user.asha_profile.assigned_village_id)
    else:
        if village_id:
            query = query.filter(Child.village_id == village_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Child.full_name.ilike(search_pattern),
                Child.rch_mcp_number.ilike(search_pattern),
                Child.mother_name.ilike(search_pattern),
                Child.father_name.ilike(search_pattern)
            )
        )

    children = query.order_by(Child.date_of_birth.desc()).all()
    results = []
    today = date.today()

    for c in children:
        metrics = VaccineEngine.calculate_child_metrics(c, c.vaccinations, today)
        
        latest_nutrition = "Normal"
        if c.growth_records:
            latest_nutrition = c.growth_records[-1].nutritional_status

        if status_filter:
            if status_filter == "overdue" and metrics["overdue_vaccines"] == 0:
                continue
            elif status_filter == "due" and metrics["due_vaccines"] == 0:
                continue
            elif status_filter == "completed" and metrics["completed_vaccines"] != metrics["total_vaccines"]:
                continue
            elif status_filter == "alert" and not metrics["has_alert"] and "SAM" not in latest_nutrition and "MAM" not in latest_nutrition:
                continue

        p_name = c.parent.user.full_name if c.parent and c.parent.user else "Parent"
        p_phone = c.parent.user.phone if c.parent and c.parent.user else (c.parent_contact or "N/A")

        summary = ChildSummaryResponse(
            id=c.id,
            parent_id=c.parent_id,
            family_id=c.family_id,
            parent_name=p_name,
            parent_phone=p_phone,
            village_id=c.village_id,
            village_name=c.village.name if c.village else "Unknown",
            full_name=c.full_name,
            date_of_birth=c.date_of_birth,
            age_formatted=metrics["age_formatted"],
            gender=c.gender,
            birth_weight_kg=c.birth_weight_kg,
            blood_group=c.blood_group,
            birth_place=c.birth_place,
            mother_name=c.mother_name,
            father_name=c.father_name,
            rch_mcp_number=c.rch_mcp_number,
            house_number=c.house_number,
            parent_contact=c.parent_contact,
            registration_date=c.registration_date,
            verification_status=c.verification_status,
            is_verified=(c.verification_status == "verified"),
            is_active=c.is_active,
            created_at=c.created_at,
            total_vaccines=metrics["total_vaccines"],
            completed_vaccines=metrics["completed_vaccines"],
            due_vaccines=metrics["due_vaccines"],
            overdue_vaccines=metrics["overdue_vaccines"],
            upcoming_vaccines=metrics["upcoming_vaccines"],
            immunization_rate=metrics["immunization_rate"],
            latest_nutritional_status=latest_nutrition,
            has_alert=metrics["has_alert"] or ("SAM" in latest_nutrition),
            alert_summary=metrics["alert_summary"]
        )
        results.append(summary)

    return results

@router.get("/{child_id}", response_model=ChildDetailResponse)
def get_child_detail(
    child_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches detailed child profile, computed immunization timeline, and health status.
    Enforces role-based isolation (Parent ownership and ASHA village jurisdiction).
    """
    child = validate_child_access(child_id, current_user, db)

    today = date.today()
    metrics = VaccineEngine.calculate_child_metrics(child, child.vaccinations, today)

    vaccination_list = []
    for rec in child.vaccinations:
        dynamic_status, days_od = VaccineEngine.compute_record_status(rec, today)
        sched = rec.vaccination_schedule

        adm_by_name = None
        if rec.administered_by_asha and rec.administered_by_asha.user:
            adm_by_name = rec.administered_by_asha.user.full_name

        vaccination_list.append(ChildVaccinationResponse(
            id=rec.id,
            child_id=rec.child_id,
            vaccination_schedule_id=rec.vaccination_schedule_id,
            vaccine_id=rec.vaccination_schedule_id,
            vaccine_name=sched.vaccine_name if sched else "Unknown",
            vaccine_code=sched.code if sched else "VAC",
            category=sched.category if sched else "General",
            recommended_timing=sched.recommended_timing if sched else "",
            target_age_label=sched.recommended_timing if sched else "",
            route=sched.route if sched else "Intramuscular",
            site=sched.site if sched else "Left arm",
            dose_amount=sched.dose_amount if sched else "0.5 ml",
            prevents_diseases=sched.prevents_diseases if sched else "",
            status=dynamic_status,
            scheduled_date=rec.scheduled_date,
            administered_date=rec.administered_date,
            administered_by_id=rec.administered_by_asha_id,
            administered_by_name=adm_by_name,
            batch_number=rec.batch_number,
            session_site=rec.session_site,
            aefi_reported=rec.aefi_reported,
            aefi_details=rec.aefi_details,
            notes=rec.notes,
            days_overdue=days_od
        ))

    latest_nutrition = "Normal"
    if child.growth_records:
        latest_nutrition = child.growth_records[-1].nutritional_status

    p_name = child.parent.user.full_name if child.parent and child.parent.user else "Parent"
    p_phone = child.parent.user.phone if child.parent and child.parent.user else (child.parent_contact or "N/A")

    return ChildDetailResponse(
        id=child.id,
        parent_id=child.parent_id,
        family_id=child.family_id,
        parent_name=p_name,
        parent_phone=p_phone,
        village_id=child.village_id,
        village_name=child.village.name if child.village else "Unknown",
        full_name=child.full_name,
        date_of_birth=child.date_of_birth,
        age_formatted=metrics["age_formatted"],
        gender=child.gender,
        birth_weight_kg=child.birth_weight_kg,
        blood_group=child.blood_group,
        birth_place=child.birth_place,
        mother_name=child.mother_name,
        father_name=child.father_name,
        rch_mcp_number=child.rch_mcp_number,
        house_number=child.house_number,
        parent_contact=child.parent_contact,
        registration_date=child.registration_date,
        verification_status=child.verification_status,
        is_verified=(child.verification_status == "verified"),
        is_active=child.is_active,
        created_at=child.created_at,
        total_vaccines=metrics["total_vaccines"],
        completed_vaccines=metrics["completed_vaccines"],
        due_vaccines=metrics["due_vaccines"],
        overdue_vaccines=metrics["overdue_vaccines"],
        upcoming_vaccines=metrics["upcoming_vaccines"],
        immunization_rate=metrics["immunization_rate"],
        latest_nutritional_status=latest_nutrition,
        has_alert=metrics["has_alert"] or ("SAM" in latest_nutrition),
        alert_summary=metrics["alert_summary"],
        immunizations=vaccination_list,
        vaccinations=vaccination_list
    )

@router.post("/{child_id}/verify")
def verify_child_registration(
    child_id: int,
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    ASHA / Admin: Verifies child registration and creates official VerificationRecord.
    """
    child = validate_child_access(child_id, current_user, db)

    child.verification_status = "verified"

    asha_profile_id = current_user.asha_profile.id if current_user.asha_profile else 1
    vr = VerificationRecord(
        child_id=child.id,
        verified_by_asha_id=asha_profile_id,
        verification_date=date.today(),
        status="verified",
        remarks="Verified by ASHA worker on field visit",
        documents_checked="Birth Certificate / MCP Card"
    )
    db.add(vr)
    db.commit()

    # Notify Parent that verification is complete
    if child.parent and child.parent.user:
        NotificationService.send_notification(
            db=db,
            user_id=child.parent.user.id,
            title=f"✓ Information Verified: {child.full_name}",
            message=f"Your child {child.full_name}'s birth records have been physically verified by ASHA worker {current_user.full_name}.",
            notification_type="verification_completed",
            priority="LOW",
            link=f"/parent.html?child_id={child.id}"
        )

    return {"message": f"Child {child.full_name} has been verified successfully.", "is_verified": True, "verification_status": "verified"}

@router.put("/{child_id}", response_model=ChildDetailResponse)
def update_child(
    child_id: int,
    child_update: ChildUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates child profile details with access validation.
    Recalculates vaccination schedule dates if date of birth is updated.
    """
    child = validate_child_access(child_id, current_user, db)

    dob_changed = False
    if child_update.date_of_birth and child_update.date_of_birth != child.date_of_birth:
        dob_changed = True
        child.date_of_birth = child_update.date_of_birth

    if child_update.full_name is not None:
        child.full_name = child_update.full_name
    if child_update.gender is not None:
        child.gender = child_update.gender
    if child_update.birth_weight_kg is not None:
        child.birth_weight_kg = child_update.birth_weight_kg
    if child_update.blood_group is not None:
        child.blood_group = child_update.blood_group
    if child_update.birth_place is not None:
        child.birth_place = child_update.birth_place
    if child_update.mother_name is not None:
        child.mother_name = child_update.mother_name
    if child_update.father_name is not None:
        child.father_name = child_update.father_name
    if child_update.house_number is not None:
        child.house_number = child_update.house_number
    if child_update.parent_contact is not None:
        child.parent_contact = child_update.parent_contact
    if child_update.notes is not None:
        child.notes = child_update.notes

    # If DOB changed, update scheduled_date for pending/unadministered doses
    if dob_changed:
        for rec in child.vaccinations:
            if rec.status != "administered" and rec.vaccination_schedule:
                rec.scheduled_date = child.date_of_birth + timedelta(days=rec.vaccination_schedule.recommended_age_days)

    audit = AuditLog(
        user_id=current_user.id,
        action="CHILD_UPDATED",
        entity_type="Child",
        entity_id=child.id,
        details=f"Updated details for child {child.full_name}"
    )
    db.add(audit)
    db.commit()
    db.refresh(child)

    # Notify ASHA worker if updated by Parent
    if current_user.role == "parent" and child.village and child.village.asha_workers:
        for asha_prof in child.village.asha_workers:
            if asha_prof.user:
                NotificationService.notify_asha_info_updated(
                    db, asha_prof.user.id, child.full_name, current_user.full_name, child.id
                )

    return get_child_detail(child.id, current_user, db)

@router.delete("/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(
    child_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes child profile with access validation.
    """
    child = validate_child_access(child_id, current_user, db)

    db.delete(child)
    db.commit()
    return None
