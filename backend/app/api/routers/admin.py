from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.core.security import get_password_hash
from backend.app.models.models import (
    User, Village, Parent, AshaWorker, AshaApplication, Child, ChildVaccination, AuditLog, LocationVillage
)
from backend.app.schemas.schemas import (
    AdminDashboardStats,
    VillageCreate,
    VillageResponse,
    UserResponse,
    AshaWorkerCreate,
    AshaWorkerResponse,
    AshaApplicationResponse,
    AuditLogResponse
)
from backend.app.services.vaccine_engine import VaccineEngine
from backend.app.api.deps import require_roles

router = APIRouter(prefix="/admin", tags=["Health Administration & Staff Management"])

@router.get("/dashboard", response_model=AdminDashboardStats)
def get_admin_dashboard(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    District & Block level health administration summary metrics.
    """
    total_villages = db.query(Village).count()
    total_ashas = db.query(AshaWorker).count()
    total_parents = db.query(Parent).count()
    children = db.query(Child).filter(Child.is_active == True).all()
    total_children = len(children)
    
    total_administered = db.query(ChildVaccination).filter(
        ChildVaccination.administered_date.isnot(None)
    ).count()

    today = date.today()
    total_overdue = 0
    fully_immunized_total = 0

    village_stats = []
    villages = db.query(Village).all()

    for v in villages:
        v_children = [c for c in children if c.village_id == v.id]
        v_total = len(v_children)
        v_fully_imm = 0
        v_overdue = 0

        for c in v_children:
            metrics = VaccineEngine.calculate_child_metrics(c, c.vaccinations, today)
            if metrics["overdue_vaccines"] > 0:
                v_overdue += 1
                total_overdue += 1
            if metrics["completed_vaccines"] == metrics["total_vaccines"] and metrics["total_vaccines"] > 0:
                v_fully_imm += 1
                fully_immunized_total += 1

        v_rate = round((v_fully_imm / v_total * 100), 1) if v_total > 0 else 0.0
        
        asha_w = v.asha_workers[0] if v.asha_workers else None
        asha_name = asha_w.user.full_name if asha_w and asha_w.user else "Unassigned"
        asha_phone = asha_w.user.phone if asha_w and asha_w.user else "N/A"

        village_stats.append({
            "village_id": v.id,
            "village_name": v.name,
            "sub_center": v.sub_center,
            "phc_name": v.phc_name,
            "asha_name": asha_name,
            "asha_phone": asha_phone,
            "total_children": v_total,
            "fully_immunized": v_fully_imm,
            "overdue_cases": v_overdue,
            "coverage_rate": v_rate
        })

    overall_rate = round((fully_immunized_total / total_children * 100), 1) if total_children > 0 else 0.0

    return AdminDashboardStats(
        total_villages=total_villages,
        total_asha_workers=total_ashas,
        total_parents=total_parents,
        total_children=total_children,
        total_vaccines_administered=total_administered,
        total_overdue_cases=total_overdue,
        overall_immunization_rate=overall_rate,
        villages_coverage=village_stats
    )

@router.get("/villages", response_model=List[VillageResponse])
def list_admin_villages(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Returns full village territory directory.
    """
    villages = db.query(Village).order_by(Village.name).all()
    results = []
    for v in villages:
        asha_w = v.asha_workers[0] if v.asha_workers else None
        asha_name = asha_w.user.full_name if asha_w and asha_w.user else None
        asha_id = asha_w.id if asha_w else None

        results.append(VillageResponse(
            id=v.id,
            name=v.name,
            sub_center=v.sub_center,
            phc_name=v.phc_name,
            district=v.district,
            state=v.state,
            pin_code=v.pin_code,
            population=v.population,
            asha_worker_id=asha_id,
            asha_worker_name=asha_name,
            created_at=v.created_at,
            total_children=len(v.children)
        ))
    return results

@router.get("/asha-applications", response_model=List[AshaApplicationResponse])
def list_asha_applications(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    applications = db.query(AshaApplication).order_by(AshaApplication.created_at.desc()).all()
    return [
        AshaApplicationResponse(
            id=a.id, full_name=a.full_name, username=a.username, phone=a.phone,
            email=a.email, location_village_id=a.location_village_id,
            village_name=a.location_village.name, status=a.status,
            qualification=a.qualification, experience_years=a.experience_years,
            created_at=a.created_at
        ) for a in applications
    ]

@router.post("/villages", response_model=VillageResponse, status_code=status.HTTP_201_CREATED)
def create_village(
    village_in: VillageCreate,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Creates a new rural village territory.
    """
    location = None
    if village_in.location_village_id:
        location = db.query(LocationVillage).filter(LocationVillage.id == village_in.location_village_id).first()
        if not location:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected real village does not exist.")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A village from the real Indian location hierarchy is required.")
    existing = db.query(Village).filter(Village.location_village_id == location.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Village already exists.")

    new_v = Village(
        name=location.name,
        sub_center=f"{location.subdistrict.name} Sub-Center",
        phc_name=f"{location.subdistrict.district.name} Primary Health Centre",
        district=location.subdistrict.district.name,
        state=location.subdistrict.district.state.name,
        pin_code=village_in.pin_code,
        population=village_in.population,
        location_village_id=location.id
    )
    db.add(new_v)
    db.commit()
    db.refresh(new_v)

    audit = AuditLog(
        user_id=current_user.id,
        action="VILLAGE_CREATED",
        entity_type="Village",
        entity_id=new_v.id,
        details=f"Created village {new_v.name} under Sub-Center {new_v.sub_center}"
    )
    db.add(audit)
    db.commit()

    return VillageResponse(
        id=new_v.id,
        name=new_v.name,
        sub_center=new_v.sub_center,
        phc_name=new_v.phc_name,
        district=new_v.district,
        state=new_v.state,
        pin_code=new_v.pin_code,
        population=new_v.population,
        asha_worker_id=None,
        asha_worker_name=None,
        created_at=new_v.created_at,
        total_children=0
    )

@router.post("/asha-workers", response_model=AshaWorkerResponse, status_code=status.HTTP_201_CREATED)
def provision_asha_worker(
    asha_in: AshaWorkerCreate,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Securely provisions an ASHA Healthcare Worker with worker code and assigned village.
    """
    existing_user = db.query(User).filter(
        (User.username == asha_in.username) | (User.phone == asha_in.phone)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or mobile number is already registered."
        )

    village = None
    if asha_in.location_village_id:
        location = db.query(LocationVillage).filter(LocationVillage.id == asha_in.location_village_id).first()
        if not location:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected location village does not exist.")
        if asha_in.location_taluka_id and location.subdistrict_id != asha_in.location_taluka_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Village does not belong to the selected taluka.")
        if asha_in.location_district_id and location.subdistrict.district_id != asha_in.location_district_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Village does not belong to the selected district.")
        if asha_in.location_state_id and location.subdistrict.district.state_id != asha_in.location_state_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Village does not belong to the selected state.")
        village = db.query(Village).filter(Village.location_village_id == location.id).first()
        if not village:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected village is not registered as an operational village yet.")
    elif asha_in.assigned_village_id:
        village = db.query(Village).filter(Village.id == asha_in.assigned_village_id).first()
    if not village:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned village does not exist.")

    # Generate worker code if not provided
    code = asha_in.worker_code
    if not code:
        code = f"ASHA-{village.name[:3].upper()}-{db.query(AshaWorker).count() + 1:02d}"

    existing_code = db.query(AshaWorker).filter(AshaWorker.worker_code == code).first()
    if existing_code:
        code = f"{code}-{int(date.today().strftime('%j'))}"

    hashed_pw = get_password_hash(asha_in.password)
    user = User(
        username=asha_in.username,
        phone=asha_in.phone,
        full_name=asha_in.full_name,
        email=asha_in.email,
        password_hash=hashed_pw,
        role="asha",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    asha_profile = AshaWorker(
        user_id=user.id,
        worker_code=code,
        assigned_village_id=village.id,
        qualification=asha_in.qualification or "Higher Secondary",
        experience_years=asha_in.experience_years,
        joined_date=date.today()
    )
    db.add(asha_profile)
    
    audit = AuditLog(
        user_id=current_user.id,
        action="ASHA_PROVISIONED",
        entity_type="AshaWorker",
        entity_id=user.id,
        details=f"Provisioned ASHA worker {user.full_name} ({code}) for village {village.name}"
    )
    db.add(audit)
    db.commit()
    db.refresh(asha_profile)

    return AshaWorkerResponse(
        id=asha_profile.id,
        user_id=user.id,
        full_name=user.full_name,
        phone=user.phone,
        email=user.email,
        worker_code=asha_profile.worker_code,
        assigned_village_id=village.id,
        assigned_village_name=village.name,
        qualification=asha_profile.qualification,
        experience_years=asha_profile.experience_years,
        is_active=user.is_active,
        joined_date=asha_profile.joined_date,
        created_at=asha_profile.created_at
    )

@router.get("/asha-workers", response_model=List[AshaWorkerResponse])
def list_asha_workers(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Lists all provisioned ASHA workers and their assigned village territories.
    """
    ashas = db.query(AshaWorker).all()
    results = []
    for a in ashas:
        results.append(AshaWorkerResponse(
            id=a.id,
            user_id=a.user_id,
            full_name=a.user.full_name if a.user else "Unknown",
            phone=a.user.phone if a.user else "N/A",
            email=a.user.email if a.user else None,
            worker_code=a.worker_code,
            assigned_village_id=a.assigned_village_id,
            assigned_village_name=a.assigned_village.name if a.assigned_village else "Unassigned",
            qualification=a.qualification,
            experience_years=a.experience_years,
            is_active=a.user.is_active if a.user else True,
            joined_date=a.joined_date,
            created_at=a.created_at
        ))
    return results

@router.put("/villages/{village_id}/assign-asha")
def assign_asha_to_village(
    village_id: int,
    asha_id: int,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Re-assigns an ASHA worker to a village jurisdiction.
    """
    village = db.query(Village).filter(Village.id == village_id).first()
    if not village:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Village not found.")

    asha = db.query(AshaWorker).filter(AshaWorker.id == asha_id).first()
    if not asha:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ASHA worker not found.")

    asha.assigned_village_id = village.id
    
    audit = AuditLog(
        user_id=current_user.id,
        action="ASHA_ASSIGNED",
        entity_type="AshaWorker",
        entity_id=asha.id,
        details=f"Assigned ASHA {asha.user.full_name} to village {village.name}"
    )
    db.add(audit)
    db.commit()

    return {"message": f"Assigned {asha.user.full_name} to {village.name} successfully."}

@router.put("/users/{user_id}/status")
def toggle_user_status(
    user_id: int,
    is_active: bool,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Activates or deactivates user account.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_active = is_active
    audit = AuditLog(
        user_id=current_user.id,
        action="USER_STATUS_TOGGLED",
        entity_type="User",
        entity_id=user.id,
        details=f"Set user {user.username} active status to {is_active}"
    )
    db.add(audit)
    db.commit()

    return {"message": f"User {user.username} status updated to {'active' if is_active else 'inactive'}."}

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = 50,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Fetches chronological audit trail.
    """
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    results = []
    for l in logs:
        results.append(AuditLogResponse(
            id=l.id,
            user_id=l.user_id,
            username=l.user.username if l.user else "System",
            action=l.action,
            entity_type=l.entity_type,
            entity_id=l.entity_id,
            details=l.details,
            ip_address=l.ip_address,
            created_at=l.created_at
        ))
    return results


@router.get("/users")
def list_all_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 200,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: List all registered users with optional role and status filters.
    """
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    users = q.order_by(User.created_at.desc()).limit(limit).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "phone": u.phone,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.get("/parents")
def list_all_parents(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: List all registered parents with family/child counts.
    """
    parents = db.query(Parent).all()
    result = []
    for p in parents:
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "full_name": p.user.full_name if p.user else "Unknown",
            "phone": p.user.phone if p.user else "N/A",
            "email": p.user.email if p.user else None,
            "occupation": p.occupation,
            "alternate_phone": p.alternate_phone,
            "total_children": len(p.children),
            "total_families": len(p.families),
            "is_active": p.user.is_active if p.user else True,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return result


@router.get("/children")
def list_all_children_admin(
    village_id: Optional[int] = None,
    verification_status: Optional[str] = None,
    limit: int = 500,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: List all registered children across all villages with vaccination summary.
    """
    q = db.query(Child).filter(Child.is_active == True)
    if village_id:
        q = q.filter(Child.village_id == village_id)
    if verification_status:
        q = q.filter(Child.verification_status == verification_status)
    children = q.order_by(Child.registration_date.desc()).limit(limit).all()

    today = date.today()
    result = []
    for c in children:
        metrics = VaccineEngine.calculate_child_metrics(c, c.vaccinations, today)
        result.append({
            "id": c.id,
            "full_name": c.full_name,
            "date_of_birth": c.date_of_birth.isoformat() if c.date_of_birth else None,
            "gender": c.gender,
            "village_name": c.village.name if c.village else "N/A",
            "village_id": c.village_id,
            "parent_name": c.parent.user.full_name if c.parent and c.parent.user else "N/A",
            "parent_phone": c.parent.user.phone if c.parent and c.parent.user else "N/A",
            "rch_mcp_number": c.rch_mcp_number,
            "verification_status": c.verification_status,
            "is_active": c.is_active,
            "registration_date": c.registration_date.isoformat() if c.registration_date else None,
            "completed_vaccines": metrics.get("completed_vaccines", 0),
            "total_vaccines": metrics.get("total_vaccines", 0),
            "overdue_vaccines": metrics.get("overdue_vaccines", 0),
            "immunization_rate": metrics.get("immunization_rate", 0.0),
        })
    return result


@router.get("/vaccination-records")
def list_vaccination_records(
    village_id: Optional[int] = None,
    record_status: Optional[str] = None,
    limit: int = 200,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Browse all child vaccination records with filters.
    status options: administered, pending, overdue
    """
    q = db.query(ChildVaccination)
    if record_status == "administered":
        q = q.filter(ChildVaccination.administered_date.isnot(None))
    elif record_status in ("pending", "overdue"):
        q = q.filter(ChildVaccination.administered_date.is_(None))
        if record_status == "overdue":
            q = q.filter(ChildVaccination.scheduled_date < date.today())
    if village_id:
        q = q.join(Child).filter(Child.village_id == village_id)
    records = q.order_by(ChildVaccination.scheduled_date.desc()).limit(limit).all()

    result = []
    for r in records:
        child = r.child
        village_name = child.village.name if child and child.village else "N/A"
        admin_name = None
        if r.administered_by_asha and r.administered_by_asha.user:
            admin_name = r.administered_by_asha.user.full_name
        vac = r.vaccination_schedule
        result.append({
            "id": r.id,
            "child_id": r.child_id,
            "child_name": child.full_name if child else "N/A",
            "village_name": village_name,
            "vaccine_name": vac.vaccine_name if vac else "N/A",
            "vaccine_code": vac.code if vac else "N/A",
            "status": r.status,
            "scheduled_date": r.scheduled_date.isoformat() if r.scheduled_date else None,
            "administered_date": r.administered_date.isoformat() if r.administered_date else None,
            "administered_by_name": admin_name,
            "batch_number": r.batch_number,
            "aefi_reported": r.aefi_reported,
        })
    return result


@router.get("/reports/summary")
def get_district_report(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: District-level aggregated immunization report with per-village breakdown.
    """
    children = db.query(Child).filter(Child.is_active == True).all()
    total_children = len(children)
    today = date.today()

    fully_immunized = 0
    partially_immunized = 0
    unimmunized = 0
    total_overdue = 0

    villages = db.query(Village).all()
    per_village = []
    for v in villages:
        v_children = [c for c in children if c.village_id == v.id]
        v_total = len(v_children)
        v_fully = 0
        v_partial = 0
        v_overdue = 0
        for c in v_children:
            m = VaccineEngine.calculate_child_metrics(c, c.vaccinations, today)
            if m["total_vaccines"] == 0:
                continue
            if m["completed_vaccines"] == m["total_vaccines"]:
                v_fully += 1
                fully_immunized += 1
            elif m["completed_vaccines"] > 0:
                v_partial += 1
                partially_immunized += 1
            else:
                unimmunized += 1
            if m["overdue_vaccines"] > 0:
                v_overdue += 1
                total_overdue += 1

        asha_w = v.asha_workers[0] if v.asha_workers else None
        per_village.append({
            "village_id": v.id,
            "village_name": v.name,
            "sub_center": v.sub_center,
            "phc_name": v.phc_name,
            "asha_name": asha_w.user.full_name if asha_w and asha_w.user else "Unassigned",
            "total_children": v_total,
            "fully_immunized": v_fully,
            "partially_immunized": v_partial,
            "overdue_cases": v_overdue,
            "coverage_rate": round(v_fully / v_total * 100, 1) if v_total > 0 else 0.0,
        })

    coverage_pct = round(fully_immunized / total_children * 100, 1) if total_children > 0 else 0.0
    return {
        "total_children": total_children,
        "fully_immunized": fully_immunized,
        "partially_immunized": partially_immunized,
        "unimmunized": unimmunized,
        "total_overdue": total_overdue,
        "coverage_percentage": coverage_pct,
        "per_village": per_village,
        "generated_on": today.isoformat(),
    }


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    new_password: str = Body(..., embed=True, min_length=6),
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Force-reset any user's password. Audit logged.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.password_hash = get_password_hash(new_password)
    audit = AuditLog(
        user_id=current_user.id,
        action="ADMIN_PASSWORD_RESET",
        entity_type="User",
        entity_id=user.id,
        details=f"Admin reset password for user {user.username} (ID {user.id})."
    )
    db.add(audit)
    db.commit()
    return {"message": f"Password reset successfully for {user.username}."}
