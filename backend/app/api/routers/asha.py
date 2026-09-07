from typing import List, Optional, Dict, Any
from datetime import date, timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.db.database import get_db
from backend.app.models.models import (
    User, Village, AshaWorker, Child, ChildVaccination, GrowthRecord, HouseVisit, Notification, AuditLog, Family, Parent
)
from backend.app.schemas.schemas import (
    AshaDashboardStats,
    PriorityFollowUpItem,
    HouseVisitCreate,
    HouseVisitResponse,
    NotificationResponse,
    FamilyResponse
)
from backend.app.services.vaccine_engine import VaccineEngine
from backend.app.api.deps import require_roles, get_current_user

router = APIRouter(prefix="/asha", tags=["ASHA Field Operations Hub"])


def _get_asha_village(current_user: User, db: Session) -> Optional[Village]:
    """Helper to resolve assigned village with fallback for admin demo."""
    if current_user.role == "asha" and current_user.asha_profile:
        return current_user.asha_profile.assigned_village
    # Fallback to first village for district admin preview
    return db.query(Village).first()


@router.get("/dashboard", response_model=AshaDashboardStats)
def get_asha_dashboard(
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Returns actionable village-level operational KPIs for the 8 dashboard cards:
    - Total Families
    - Total Children
    - Vaccinations Completed
    - Vaccinations Due
    - Vaccinations Overdue
    - Upcoming Vaccinations
    - Pending Verification
    - Today's Follow-ups
    """
    village = _get_asha_village(current_user, db)
    if not village:
        return AshaDashboardStats(
            village_name="No Village Assigned",
            sub_center="N/A",
            phc_name="N/A",
            total_families=0,
            total_children=0,
            total_registered_children=0,
            vaccinations_completed=0,
            vaccinations_due=0,
            vaccinations_overdue=0,
            upcoming_vaccinations=0,
            pending_verification=0,
            todays_followups=0,
            fully_immunized_children=0,
            partially_immunized_children=0,
            overdue_children_count=0,
            due_this_month_count=0,
            malnourished_children_count=0,
            coverage_percentage=0.0,
            unverified_registrations_count=0
        )

    # 1. Total Families
    total_families = db.query(Family).filter(Family.village_id == village.id).count()

    # 2. Children
    children = db.query(Child).filter(
        Child.village_id == village.id,
        Child.is_active == True
    ).all()
    total_children = len(children)

    # Aggregate Dose Counts across all children in village
    total_completed = 0
    total_due = 0
    total_overdue = 0
    total_upcoming = 0
    pending_verification = 0
    overdue_children_count = 0
    due_children_count = 0
    fully_immunized = 0
    partially_immunized = 0
    malnourished_count = 0

    today = date.today()

    for c in children:
        if c.verification_status != "verified":
            pending_verification += 1

        metrics = VaccineEngine.calculate_child_metrics(c, c.vaccinations, today)
        total_completed += metrics["completed_vaccines"]
        total_due += metrics["due_vaccines"]
        total_overdue += metrics["overdue_vaccines"]
        total_upcoming += metrics["upcoming_vaccines"]

        if metrics["overdue_vaccines"] > 0:
            overdue_children_count += 1
        if metrics["due_vaccines"] > 0:
            due_children_count += 1

        if metrics["completed_vaccines"] == metrics["total_vaccines"] and metrics["total_vaccines"] > 0:
            fully_immunized += 1
        elif metrics["completed_vaccines"] > 0:
            partially_immunized += 1

        if c.growth_records:
            latest_status = c.growth_records[-1].nutritional_status
            if latest_status and ("SAM" in latest_status or "MAM" in latest_status or "Severe" in latest_status):
                malnourished_count += 1

    # 3. Today's Follow-ups (scheduled visits today + overdue visits)
    todays_followups = db.query(HouseVisit).join(Child).filter(
        Child.village_id == village.id,
        (HouseVisit.visit_date == today) | 
        ((HouseVisit.status == "scheduled") & (HouseVisit.visit_date <= today))
    ).count()

    coverage = round((fully_immunized / total_children * 100), 1) if total_children > 0 else 0.0

    return AshaDashboardStats(
        village_name=village.name,
        sub_center=village.sub_center,
        phc_name=village.phc_name,
        total_families=total_families,
        total_children=total_children,
        total_registered_children=total_children,
        vaccinations_completed=total_completed,
        vaccinations_due=total_due,
        vaccinations_overdue=total_overdue,
        upcoming_vaccinations=total_upcoming,
        pending_verification=pending_verification,
        todays_followups=todays_followups,
        fully_immunized_children=fully_immunized,
        partially_immunized_children=partially_immunized,
        overdue_children_count=overdue_children_count,
        due_this_month_count=due_children_count,
        malnourished_children_count=malnourished_count,
        coverage_percentage=coverage,
        unverified_registrations_count=pending_verification
    )


@router.get("/follow-ups")
@router.get("/priority-follow-ups", response_model=List[PriorityFollowUpItem])
def get_priority_follow_ups(
    priority: Optional[str] = Query(None, description="Filter by HIGH, MEDIUM, LOW, or None (all)"),
    filter_type: Optional[str] = Query(None, description="Backward compatibility filter: all, overdue, due_soon"),
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Generates categorized, actionable Priority Follow-ups for ASHA workers:

    HIGH Priority:
      - Overdue vaccination (>28 days past due date)
      - Critical malnutrition alert (SAM/MAM)
      - Information requiring field verification

    MEDIUM Priority:
      - Vaccination approaching / due now (within [-14, +28] day window)
      - Incomplete child profile information (missing contact/house/weight)

    LOW Priority:
      - Routine follow-up & scheduled growth monitoring check
    """
    village = _get_asha_village(current_user, db)
    if not village:
        return []

    children = db.query(Child).filter(
        Child.village_id == village.id,
        Child.is_active == True
    ).all()

    today = date.today()
    priority_items: List[PriorityFollowUpItem] = []

    for c in children:
        p_name = c.parent.user.full_name if c.parent and c.parent.user else (c.mother_name or c.father_name or "Parent")
        p_phone = c.parent.user.phone if c.parent and c.parent.user else (c.parent_contact or "No contact")
        p_house = c.house_number or (c.family.house_number if c.family else "N/A")
        p_address = c.family.address if c.family and c.family.address else (c.house_number or village.name)
        age_str = VaccineEngine.format_child_age(c.date_of_birth, today)

        overdue_vacs = []
        due_vacs = []

        for rec in c.vaccinations:
            st, days_od = VaccineEngine.compute_record_status(rec, today)
            vac_name = rec.vaccination_schedule.vaccine_name if rec.vaccination_schedule else "Vaccine"
            if st == "overdue":
                overdue_vacs.append((vac_name, rec.scheduled_date, days_od))
            elif st == "due":
                due_vacs.append((vac_name, rec.scheduled_date))

        # 1. HIGH: Overdue vaccinations
        if overdue_vacs:
            most_od = max(overdue_vacs, key=lambda x: x[2])
            vac_list_str = ", ".join([f"{v[0]} ({v[2]}d late)" for v in overdue_vacs])
            vac_names_only = [v[0] for v in overdue_vacs]
            wa_text = (
                f"Namaste {p_name}, this is ASHA worker {current_user.full_name} from {village.name}. "
                f"Urgent reminder: Child {c.full_name} has overdue vaccinations: {', '.join(vac_names_only)}. "
                f"Please bring your MCP card to the nearest Health Sub-Center immediately."
            )
            priority_items.append(PriorityFollowUpItem(
                id=f"high-overdue-{c.id}",
                child_id=c.id,
                child_name=c.full_name,
                age_formatted=age_str,
                parent_name=p_name,
                parent_phone=p_phone,
                village_name=village.name,
                house_number=p_house,
                address=p_address,
                reason=f"Overdue vaccination ({len(overdue_vacs)} doses): {vac_list_str}",
                priority="HIGH",
                category_type="overdue_vaccine",
                due_date=most_od[1].isoformat(),
                overdue_days=most_od[2],
                vaccine_names=vac_names_only,
                whatsapp_message=wa_text
            ))

        # 2. HIGH: Information requiring field verification
        if c.verification_status != "verified":
            priority_items.append(PriorityFollowUpItem(
                id=f"high-verify-{c.id}",
                child_id=c.id,
                child_name=c.full_name,
                age_formatted=age_str,
                parent_name=p_name,
                parent_phone=p_phone,
                village_name=village.name,
                house_number=p_house,
                address=p_address,
                reason="New self-registration requires physical verification of birth details & MCP card",
                priority="HIGH",
                category_type="unverified_info",
                due_date=c.registration_date.isoformat() if c.registration_date else today.isoformat(),
                overdue_days=(today - c.registration_date).days if c.registration_date else 0,
                vaccine_names=[],
                whatsapp_message=f"Namaste {p_name}, ASHA worker {current_user.full_name} will visit your home in {village.name} to verify child registration documents."
            ))

        # 3. MEDIUM: Approaching / Due Vaccinations
        if due_vacs and not overdue_vacs:
            vac_names_only = [v[0] for v in due_vacs]
            earliest_due = min(due_vacs, key=lambda x: x[1])
            wa_text = (
                f"Namaste {p_name}, ASHA worker {current_user.full_name} from {village.name}. "
                f"Upcoming vaccination due for {c.full_name}: {', '.join(vac_names_only)}. "
                f"Scheduled for {earliest_due[1].strftime('%d %b %Y')}. Please visit the upcoming session."
            )
            priority_items.append(PriorityFollowUpItem(
                id=f"med-due-{c.id}",
                child_id=c.id,
                child_name=c.full_name,
                age_formatted=age_str,
                parent_name=p_name,
                parent_phone=p_phone,
                village_name=village.name,
                house_number=p_house,
                address=p_address,
                reason=f"Vaccination due now: {', '.join(vac_names_only)}",
                priority="MEDIUM",
                category_type="due_soon",
                due_date=earliest_due[1].isoformat(),
                overdue_days=0,
                vaccine_names=vac_names_only,
                whatsapp_message=wa_text
            ))

        # 4. MEDIUM: Incomplete Profile Information
        incomplete_fields = []
        if not c.birth_weight_kg:
            incomplete_fields.append("birth weight")
        if not c.mother_name and not c.father_name:
            incomplete_fields.append("parent names")
        if not c.rch_mcp_number:
            incomplete_fields.append("MCP card ID")

        if incomplete_fields and c.verification_status == "verified":
            priority_items.append(PriorityFollowUpItem(
                id=f"med-incomplete-{c.id}",
                child_id=c.id,
                child_name=c.full_name,
                age_formatted=age_str,
                parent_name=p_name,
                parent_phone=p_phone,
                village_name=village.name,
                house_number=p_house,
                address=p_address,
                reason=f"Incomplete record: Missing {', '.join(incomplete_fields)}",
                priority="MEDIUM",
                category_type="incomplete_info",
                due_date=today.isoformat(),
                overdue_days=0,
                vaccine_names=[],
                whatsapp_message=f"Namaste {p_name}, please update {', '.join(incomplete_fields)} for {c.full_name} during the next ASHA visit."
            ))

        # 5. LOW: Routine Follow-up
        if not overdue_vacs and not due_vacs and c.verification_status == "verified":
            priority_items.append(PriorityFollowUpItem(
                id=f"low-routine-{c.id}",
                child_id=c.id,
                child_name=c.full_name,
                age_formatted=age_str,
                parent_name=p_name,
                parent_phone=p_phone,
                village_name=village.name,
                house_number=p_house,
                address=p_address,
                reason="Routine monthly growth monitoring and maternal-child health check",
                priority="LOW",
                category_type="routine",
                due_date=(today + timedelta(days=14)).isoformat(),
                overdue_days=0,
                vaccine_names=[],
                whatsapp_message=f"Namaste {p_name}, routine health & nutrition check is scheduled for {c.full_name}."
            ))

    # Apply priority filter if given
    if priority and priority.upper() in ["HIGH", "MEDIUM", "LOW"]:
        priority_items = [item for item in priority_items if item.priority == priority.upper()]

    # Sort: HIGH first, then by overdue days descending, then MEDIUM, then LOW
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    priority_items.sort(key=lambda x: (priority_order.get(x.priority, 3), -x.overdue_days))

    return priority_items


@router.get("/families", response_model=List[FamilyResponse])
def get_village_families(
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Returns all registered families in the ASHA worker's assigned village.
    """
    village = _get_asha_village(current_user, db)
    if not village:
        return []

    families = db.query(Family).filter(Family.village_id == village.id).all()
    results = []
    for f in families:
        results.append(FamilyResponse(
            id=f.id,
            parent_id=f.parent_id,
            village_id=f.village_id,
            village_name=village.name,
            family_head_name=f.family_head_name,
            ration_card_number=f.ration_card_number,
            house_number=f.house_number,
            address=f.address,
            contact_number=f.contact_number,
            socioeconomic_category=f.socioeconomic_category,
            total_children=len(f.children),
            created_at=f.created_at
        ))
    return results


@router.get("/house-visits", response_model=List[HouseVisitResponse])
def get_house_visits(
    category: Optional[str] = Query(None, description="today, upcoming, pending, completed, all"),
    priority: Optional[str] = Query(None, description="HIGH, MEDIUM, LOW"),
    status_filter: Optional[str] = Query(None, description="scheduled, completed, rescheduled, cancelled"),
    child_id: Optional[int] = Query(None),
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Returns list of targeted house visits in the assigned village.
    Filters:
      - today: Visits scheduled on today's date
      - upcoming: Visits scheduled for future dates
      - pending: Scheduled visits whose date has passed (missed/overdue)
      - completed: Finished counseling logs
    """
    village = _get_asha_village(current_user, db)
    if not village:
        return []

    query = db.query(HouseVisit).join(Child).filter(Child.village_id == village.id)
    today = date.today()

    if child_id:
        query = query.filter(HouseVisit.child_id == child_id)

    if priority:
        query = query.filter(HouseVisit.priority == priority.upper())

    if status_filter:
        query = query.filter(HouseVisit.status == status_filter)

    # Category filters for reduction of unnecessary visits
    if category == "today":
        query = query.filter(HouseVisit.visit_date == today, HouseVisit.status != "cancelled")
    elif category == "upcoming":
        query = query.filter(HouseVisit.visit_date > today, HouseVisit.status != "completed", HouseVisit.status != "cancelled")
    elif category == "pending":
        query = query.filter(HouseVisit.visit_date < today, HouseVisit.status == "scheduled")
    elif category == "completed":
        query = query.filter(HouseVisit.status == "completed")

    visits = query.order_by(HouseVisit.visit_date.desc()).all()
    results = []
    for v in visits:
        c = v.child
        f_name = c.parent.user.full_name if c and c.parent and c.parent.user else (c.mother_name or c.father_name if c else "Family")
        h_no = c.house_number if c else "N/A"
        p_phone = c.parent_contact or (c.parent.user.phone if c and c.parent and c.parent.user else None)

        results.append(HouseVisitResponse(
            id=v.id,
            child_id=v.child_id,
            child_name=c.full_name if c else "Unknown Child",
            family_id=v.family_id,
            family_head_name=f_name,
            house_number=h_no,
            parent_contact=p_phone,
            asha_worker_id=v.asha_worker_id,
            asha_name=v.asha_worker.user.full_name if v.asha_worker and v.asha_worker.user else current_user.full_name,
            visit_date=v.visit_date,
            reason=v.reason,
            priority=v.priority or "MEDIUM",
            observations=v.observations,
            remarks=v.remarks,
            action_taken=v.action_taken,
            next_visit_date=v.next_visit_date,
            status=v.status,
            notes=v.notes,
            completed_at=v.completed_at,
            created_at=v.created_at
        ))
    return results


@router.get("/house-visits/counts")
def get_house_visit_counts(
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Returns counts for Today's, Upcoming, Pending, and Completed visits to give immediate field focus.
    """
    village = _get_asha_village(current_user, db)
    if not village:
        return {"today": 0, "upcoming": 0, "pending": 0, "completed": 0, "total": 0}

    today = date.today()
    base_query = db.query(HouseVisit).join(Child).filter(Child.village_id == village.id)

    today_count = base_query.filter(HouseVisit.visit_date == today, HouseVisit.status != "cancelled").count()
    upcoming_count = base_query.filter(HouseVisit.visit_date > today, HouseVisit.status != "completed", HouseVisit.status != "cancelled").count()
    pending_count = base_query.filter(HouseVisit.visit_date < today, HouseVisit.status == "scheduled").count()
    completed_count = base_query.filter(HouseVisit.status == "completed").count()

    return {
        "today": today_count,
        "upcoming": upcoming_count,
        "pending": pending_count,
        "completed": completed_count,
        "total": today_count + upcoming_count + pending_count + completed_count
    }


def _determine_visit_priority(reason: str) -> str:
    """Priority algorithm mapping."""
    r_lower = reason.lower()
    if "overdue" in r_lower or "verification" in r_lower or "sam" in r_lower:
        return "HIGH"
    if "approaching" in r_lower or "incomplete" in r_lower or "follow-up" in r_lower:
        return "MEDIUM"
    return "LOW"


@router.post("/house-visits", response_model=HouseVisitResponse, status_code=status.HTTP_201_CREATED)
@router.post("/follow-up-notes", response_model=HouseVisitResponse, status_code=status.HTTP_201_CREATED)
def create_house_visit(
    visit_in: HouseVisitCreate,
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Creates a new targeted house visit.
    Automatically assigns priority if not explicitly specified.
    """
    child = db.query(Child).filter(Child.id == visit_in.child_id).first()
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found.")

    if current_user.role == "asha":
        if not current_user.asha_profile or child.village_id != current_user.asha_profile.assigned_village_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. ASHA workers can only log house visits for children in their assigned village."
            )

    asha_profile_id = current_user.asha_profile.id if current_user.asha_profile else 1
    priority = visit_in.priority or _determine_visit_priority(visit_in.reason)

    is_completed = visit_in.status == "completed"
    completed_at = datetime.now(timezone.utc) if is_completed else None

    new_visit = HouseVisit(
        child_id=child.id,
        family_id=child.family_id,
        asha_worker_id=asha_profile_id,
        visit_date=visit_in.visit_date,
        reason=visit_in.reason,
        priority=priority,
        observations=visit_in.observations,
        remarks=visit_in.remarks or "Field visit scheduled",
        action_taken=visit_in.action_taken,
        next_visit_date=visit_in.next_visit_date,
        notes=visit_in.notes,
        status=visit_in.status,
        completed_at=completed_at
    )
    db.add(new_visit)
    db.commit()
    db.refresh(new_visit)

    f_name = child.parent.user.full_name if child.parent and child.parent.user else "Family"

    return HouseVisitResponse(
        id=new_visit.id,
        child_id=new_visit.child_id,
        child_name=child.full_name,
        family_id=new_visit.family_id,
        family_head_name=f_name,
        house_number=child.house_number,
        parent_contact=child.parent_contact,
        asha_worker_id=new_visit.asha_worker_id,
        asha_name=current_user.full_name,
        visit_date=new_visit.visit_date,
        reason=new_visit.reason,
        priority=new_visit.priority,
        observations=new_visit.observations,
        remarks=new_visit.remarks,
        action_taken=new_visit.action_taken,
        next_visit_date=new_visit.next_visit_date,
        status=new_visit.status,
        notes=new_visit.notes,
        completed_at=new_visit.completed_at,
        created_at=new_visit.created_at
    )


@router.put("/house-visits/{visit_id}/reschedule", response_model=HouseVisitResponse)
def reschedule_house_visit(
    visit_id: int,
    new_visit_date: date = Query(..., description="New scheduled date for visit"),
    reason: Optional[str] = Query(None, description="Reason for rescheduling"),
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Reschedules a house visit to a new date.
    """
    visit = db.query(HouseVisit).filter(HouseVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="House visit record not found.")

    child = visit.child
    if current_user.role == "asha" and child:
        if not current_user.asha_profile or child.village_id != current_user.asha_profile.assigned_village_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    old_date = visit.visit_date
    visit.visit_date = new_visit_date
    visit.status = "rescheduled"
    resched_note = f"Rescheduled from {old_date} to {new_visit_date}. Reason: {reason or 'Family request / session alignment'}."
    visit.notes = f"{visit.notes or ''}\n{resched_note}".strip()

    db.commit()
    db.refresh(visit)

    return HouseVisitResponse(
        id=visit.id,
        child_id=visit.child_id,
        child_name=child.full_name if child else "Child",
        family_id=visit.family_id,
        family_head_name=child.parent.user.full_name if child and child.parent and child.parent.user else "Family",
        house_number=child.house_number if child else "N/A",
        parent_contact=child.parent_contact if child else None,
        asha_worker_id=visit.asha_worker_id,
        asha_name=current_user.full_name,
        visit_date=visit.visit_date,
        reason=visit.reason,
        priority=visit.priority or "MEDIUM",
        observations=visit.observations,
        remarks=visit.remarks,
        action_taken=visit.action_taken,
        next_visit_date=visit.next_visit_date,
        status=visit.status,
        notes=visit.notes,
        completed_at=visit.completed_at,
        created_at=visit.created_at
    )


@router.put("/house-visits/{visit_id}/complete", response_model=HouseVisitResponse)
def complete_house_visit(
    visit_id: int,
    remarks: str = Query(..., description="Observations and counseling notes"),
    action_taken: Optional[str] = Query(None),
    next_visit_date: Optional[date] = Query(None),
    notes: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Marks a house visit completed and records timestamp and observations.
    """
    visit = db.query(HouseVisit).filter(HouseVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="House visit record not found.")

    child = visit.child
    if current_user.role == "asha" and child:
        if not current_user.asha_profile or child.village_id != current_user.asha_profile.assigned_village_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    visit.status = "completed"
    visit.completed_at = datetime.now(timezone.utc)
    visit.remarks = remarks
    if action_taken:
        visit.action_taken = action_taken
    if next_visit_date:
        visit.next_visit_date = next_visit_date
    if notes:
        visit.notes = f"{visit.notes or ''}\n{notes}".strip()

    db.commit()
    db.refresh(visit)

    return HouseVisitResponse(
        id=visit.id,
        child_id=visit.child_id,
        child_name=child.full_name if child else "Child",
        family_id=visit.family_id,
        family_head_name=child.parent.user.full_name if child and child.parent and child.parent.user else "Family",
        house_number=child.house_number if child else "N/A",
        parent_contact=child.parent_contact if child else None,
        asha_worker_id=visit.asha_worker_id,
        asha_name=current_user.full_name,
        visit_date=visit.visit_date,
        reason=visit.reason,
        priority=visit.priority or "MEDIUM",
        observations=visit.observations,
        remarks=visit.remarks,
        action_taken=visit.action_taken,
        next_visit_date=visit.next_visit_date,
        status=visit.status,
        notes=visit.notes,
        completed_at=visit.completed_at,
        created_at=visit.created_at
    )


@router.post("/house-visits/smart-plan")
def generate_smart_visit_plan(
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    SMART VISIT RECOMMENDER:
    Intelligently scans the village registry to identify families that ACTUALLY require a visit,
    eliminating wasted door-to-door visits for children who are up to date.

    Algorithm:
      1. Overdue vaccination (>28 days) -> HIGH priority visit
      2. Pending verification -> HIGH priority visit
      3. Approaching due vaccine (<14 days) -> MEDIUM priority visit
      4. Incomplete records -> MEDIUM priority visit
      5. Up-to-date, verified children -> NO visit needed (saved time!)
    """
    village = _get_asha_village(current_user, db)
    if not village:
        return {"created_visits": 0, "message": "No village assigned."}

    children = db.query(Child).filter(Child.village_id == village.id, Child.is_active == True).all()
    today = date.today()
    asha_id = current_user.asha_profile.id if current_user.asha_profile else 1

    created_count = 0
    skipped_count = 0

    for c in children:
        # Check if active scheduled visit already exists
        existing = db.query(HouseVisit).filter(
            HouseVisit.child_id == c.id,
            HouseVisit.status.in_(["scheduled", "rescheduled"]),
            HouseVisit.visit_date >= today
        ).first()
        if existing:
            continue

        metrics = VaccineEngine.calculate_child_metrics(c, c.vaccinations, today)

        visit_needed = False
        reason = ""
        priority = "LOW"

        if metrics["overdue_vaccines"] > 0:
            visit_needed = True
            reason = "Vaccination overdue"
            priority = "HIGH"
        elif c.verification_status != "verified":
            visit_needed = True
            reason = "Information verification"
            priority = "HIGH"
        elif metrics["due_vaccines"] > 0:
            visit_needed = True
            reason = "Vaccination follow-up"
            priority = "MEDIUM"
        elif not c.birth_weight_kg or not c.mother_name:
            visit_needed = True
            reason = "Child information incomplete"
            priority = "MEDIUM"
        else:
            skipped_count += 1  # Unnecessary visit successfully eliminated!

        if visit_needed:
            new_v = HouseVisit(
                child_id=c.id,
                family_id=c.family_id,
                asha_worker_id=asha_id,
                visit_date=today,
                reason=reason,
                priority=priority,
                remarks=f"Auto-prioritized visit: {reason}",
                status="scheduled",
                notes="Generated by Digital ASHA Smart Visit Recommender to eliminate unnecessary door-to-door visits."
            )
            db.add(new_v)
            created_count += 1

    db.commit()
    return {
        "created_visits": created_count,
        "unnecessary_visits_saved": skipped_count,
        "message": f"Generated {created_count} targeted visits. Eliminated {skipped_count} unnecessary home visits!"
    }


@router.get("/reports")
def get_village_reports(
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Generates official monthly village immunization & health monitoring report for ASHA submission.
    """
    village = _get_asha_village(current_user, db)
    if not village:
        return {"error": "No village assigned"}

    children = db.query(Child).filter(Child.village_id == village.id, Child.is_active == True).all()
    today = date.today()

    total_children = len(children)
    fully_immunized = 0
    partially_immunized = 0
    unimmunized = 0

    category_stats: Dict[str, Dict[str, int]] = {}
    nutrition_breakdown = {"Normal": 0, "MAM": 0, "SAM": 0, "Not Measured": 0}

    for c in children:
        metrics = VaccineEngine.calculate_child_metrics(c, c.vaccinations, today)
        if metrics["completed_vaccines"] == metrics["total_vaccines"] and metrics["total_vaccines"] > 0:
            fully_immunized += 1
        elif metrics["completed_vaccines"] > 0:
            partially_immunized += 1
        else:
            unimmunized += 1

        for v in c.vaccinations:
            cat = v.vaccination_schedule.category if v.vaccination_schedule else "Other"
            if cat not in category_stats:
                category_stats[cat] = {"scheduled": 0, "administered": 0, "overdue": 0}
            category_stats[cat]["scheduled"] += 1
            if v.administered_date:
                category_stats[cat]["administered"] += 1
            elif (today - v.scheduled_date).days > 28:
                category_stats[cat]["overdue"] += 1

        if c.growth_records:
            st = c.growth_records[-1].nutritional_status or "Normal"
            if "SAM" in st or "Severe" in st:
                nutrition_breakdown["SAM"] += 1
            elif "MAM" in st or "Moderate" in st:
                nutrition_breakdown["MAM"] += 1
            else:
                nutrition_breakdown["Normal"] += 1
        else:
            nutrition_breakdown["Not Measured"] += 1

    coverage_rate = round((fully_immunized / total_children * 100), 1) if total_children > 0 else 0.0

    return {
        "village_name": village.name,
        "sub_center": village.sub_center,
        "phc_name": village.phc_name,
        "district": village.district,
        "state": village.state,
        "generated_on": today.isoformat(),
        "summary": {
            "total_registered_children": total_children,
            "fully_immunized": fully_immunized,
            "partially_immunized": partially_immunized,
            "unimmunized": unimmunized,
            "coverage_percentage": coverage_rate
        },
        "category_breakdown": category_stats,
        "nutrition_breakdown": nutrition_breakdown
    }


@router.get("/notifications", response_model=List[NotificationResponse])
def get_user_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns user notifications for the authenticated user.
    """
    notes = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(30).all()
    return notes


@router.post("/notifications/{notif_id}/read")
def mark_notification_as_read(
    notif_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marks a notification as read.
    """
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    notif.is_read = True
    db.commit()
    return {"message": "Notification marked as read."}
