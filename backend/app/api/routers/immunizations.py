from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.models import ChildVaccination, Child, User, AuditLog, VaccinationSchedule
from backend.app.schemas.schemas import (
    ChildVaccinationAdminister,
    ChildVaccinationResponse
)
from backend.app.services.vaccine_engine import VaccineEngine
from backend.app.services.notification_service import NotificationService
from backend.app.api.deps import get_current_user, require_roles, validate_child_access

router = APIRouter(prefix="/immunizations", tags=["Immunizations & MCP Card"])


@router.get("/timeline/{child_id}")
def get_vaccination_timeline(
    child_id: int,
    status_filter: Optional[str] = Query(None, description="Filter: all, upcoming, due, overdue, administered"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the full vaccination timeline for a child.
    Status is ALWAYS computed by the backend — never trusted from the DB cache.
    Schedule comes from the vaccination_schedules database table (not hardcoded).

    Accessible by: Parent (own children), ASHA Worker (their village), Admin (all)
    """
    child = validate_child_access(child_id, current_user, db)
    today = date.today()

    timeline = VaccineEngine.compute_vaccination_timeline(
        child=child,
        records=child.vaccinations,
        current_date=today,
        status_filter=status_filter
    )

    metrics = VaccineEngine.calculate_child_metrics(child, child.vaccinations, today)

    return {
        "child_id": child.id,
        "child_name": child.full_name,
        "date_of_birth": child.date_of_birth.isoformat(),
        "age": metrics["age_formatted"],
        "rch_mcp_number": child.rch_mcp_number,
        "village_name": child.village.name if child.village else "N/A",
        "metrics": metrics,
        "timeline": timeline,
        "schedule_source": "vaccination_schedules (database)",
        "schedule_version": "India UIP - National Immunization Schedule",
        "computed_at": today.isoformat()
    }


@router.post("/{record_id}/administer", response_model=ChildVaccinationResponse)
def record_administered_dose(
    record_id: int,
    administer_data: ChildVaccinationAdminister,
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    ASHA / Admin: Mark a vaccine dose as Administered.
    - Stores actual vaccination date (not the scheduled date)
    - Records who administered the vaccine (ASHA worker ID)
    - Stores batch number and session site
    - Updates status to 'administered'
    - Writes audit trail

    Enforces territory check: ASHA can only administer for children in their assigned village.
    """
    record = db.query(ChildVaccination).filter(ChildVaccination.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vaccination record not found.")

    child = record.child
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child record not found.")

    # Strict ASHA territory enforcement
    if current_user.role == "asha":
        if not current_user.asha_profile or child.village_id != current_user.asha_profile.assigned_village_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. ASHA workers can only record vaccinations for children in their assigned village jurisdiction."
            )

    if record.administered_date is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This dose was already administered on {record.administered_date}."
        )

    asha_worker_id = current_user.asha_profile.id if current_user.asha_profile else None

    # Update record with actual administration details
    record.administered_date = administer_data.administered_date
    record.status = "administered"
    record.administered_by_asha_id = asha_worker_id
    record.batch_number = administer_data.batch_number
    record.session_site = administer_data.session_site
    record.aefi_reported = administer_data.aefi_reported
    record.aefi_details = administer_data.aefi_details
    record.notes = administer_data.notes

    # Notify parent
    if child.parent and child.parent.user:
        vac_name = record.vaccination_schedule.vaccine_name if record.vaccination_schedule else "Vaccine"
        NotificationService.send_notification(
            db=db,
            user_id=child.parent.user.id,
            title="✅ Vaccination Recorded",
            message=(
                f"{vac_name} was successfully given to {child.full_name} "
                f"on {administer_data.administered_date.strftime('%d %b %Y')} "
                f"at {administer_data.session_site or 'Health Center'}."
            ),
            notification_type="administered"
        )

    # Audit trail
    audit = AuditLog(
        user_id=current_user.id,
        action="VACCINE_ADMINISTERED",
        entity_type="ChildVaccination",
        entity_id=record.id,
        details=(
            f"Administered {record.vaccination_schedule.vaccine_name if record.vaccination_schedule else 'Vaccine'} "
            f"to {child.full_name} (Child ID: {child.id}) "
            f"on {administer_data.administered_date} "
            f"by {current_user.full_name} "
            f"Batch: {administer_data.batch_number or 'N/A'}"
        )
    )
    db.add(audit)
    db.commit()
    db.refresh(record)

    sched = record.vaccination_schedule
    today = date.today()
    dynamic_status, days_od = VaccineEngine.compute_record_status(record, today)

    return ChildVaccinationResponse(
        id=record.id,
        child_id=record.child_id,
        vaccination_schedule_id=record.vaccination_schedule_id,
        vaccine_id=record.vaccination_schedule_id,
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
        scheduled_date=record.scheduled_date,
        administered_date=record.administered_date,
        administered_by_id=record.administered_by_asha_id,
        administered_by_name=current_user.full_name,
        batch_number=record.batch_number,
        session_site=record.session_site,
        aefi_reported=record.aefi_reported,
        aefi_details=record.aefi_details,
        notes=record.notes,
        days_overdue=0
    )


@router.get("/mcp-card/{child_id}")
def get_mcp_card_data(
    child_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the full official Mother & Child Protection (MCP) card payload.
    All vaccine schedule data is fetched from DB, not hardcoded.
    Enforces parent ownership / ASHA territory access.
    """
    child = validate_child_access(child_id, current_user, db)
    today = date.today()
    metrics = VaccineEngine.calculate_child_metrics(child, child.vaccinations, today)

    # Group vaccines by UIP Category (from DB)
    grouped_vaccines = {}
    for rec in child.vaccinations:
        sched = rec.vaccination_schedule
        if not sched:
            continue
        cat = sched.category
        if cat not in grouped_vaccines:
            grouped_vaccines[cat] = []

        dynamic_status, days_od = VaccineEngine.compute_record_status(rec, today)
        adm_by = (
            rec.administered_by_asha.user.full_name
            if rec.administered_by_asha and rec.administered_by_asha.user
            else None
        )

        grouped_vaccines[cat].append({
            "record_id": rec.id,
            "vaccine_name": sched.vaccine_name,
            "vaccine_code": sched.code,
            "dose_number": sched.dose_number,
            "dose_amount": sched.dose_amount,
            "route": sched.route,
            "site": sched.site,
            "prevents_diseases": sched.prevents_diseases,
            "scheduled_date": rec.scheduled_date.isoformat(),
            "administered_date": rec.administered_date.isoformat() if rec.administered_date else None,
            "status": dynamic_status,
            "status_label": VaccineEngine._status_label(dynamic_status, days_od),
            "days_overdue": days_od,
            "batch_number": rec.batch_number,
            "session_site": rec.session_site,
            "administered_by": adm_by,
            "aefi_reported": rec.aefi_reported,
            "aefi_details": rec.aefi_details
        })

    # ASHA worker info for this village
    asha_info = None
    if child.village and child.village.asha_workers:
        asha = child.village.asha_workers[0]
        asha_info = {
            "name": asha.user.full_name if asha.user else "ASHA Worker",
            "phone": asha.user.phone if asha.user else "",
            "worker_code": asha.worker_code,
            "sub_center": child.village.sub_center,
            "phc_name": child.village.phc_name
        }

    # Define category display order (from DB order_index)
    category_order = ["Birth", "6 Weeks", "10 Weeks", "14 Weeks",
                      "9-12 Months", "16-24 Months", "5-6 Years",
                      "10 Years", "16 Years"]
    ordered_grouped = {
        cat: grouped_vaccines[cat]
        for cat in category_order
        if cat in grouped_vaccines
    }
    # Add any categories not in the predefined order
    for cat in grouped_vaccines:
        if cat not in ordered_grouped:
            ordered_grouped[cat] = grouped_vaccines[cat]

    return {
        "child": {
            "id": child.id,
            "full_name": child.full_name,
            "date_of_birth": child.date_of_birth.isoformat(),
            "age": metrics["age_formatted"],
            "gender": child.gender,
            "birth_weight_kg": child.birth_weight_kg,
            "blood_group": child.blood_group,
            "birth_place": child.birth_place,
            "mother_name": child.mother_name,
            "father_name": child.father_name,
            "rch_mcp_number": child.rch_mcp_number,
            "house_number": child.house_number,
            "parent_contact": child.parent_contact,
            "village_name": child.village.name if child.village else "Unknown",
            "sub_center": child.village.sub_center if child.village else "N/A",
            "phc_name": child.village.phc_name if child.village else "N/A",
            "district": child.village.district if child.village else "N/A",
            "state": child.village.state if child.village else "N/A",
            "verification_status": child.verification_status,
            "is_verified": child.verification_status == "verified",
            "registration_date": child.registration_date.isoformat() if child.registration_date else None
        },
        "metrics": metrics,
        "asha_worker": asha_info,
        "grouped_schedule": ordered_grouped,
        "growth_history": [
            {
                "date": g.recorded_date.isoformat(),
                "weight_kg": g.weight_kg,
                "height_cm": g.height_cm,
                "muac_cm": g.muac_cm,
                "status": g.nutritional_status,
                "notes": g.notes
            }
            for g in child.growth_records
        ],
        "schedule_source": "vaccination_schedules (database table)",
        "generated_at": today.isoformat()
    }
