from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.models.models import VaccinationSchedule, User, AuditLog
from backend.app.schemas.schemas import VaccinationScheduleResponse, VaccinationScheduleCreate, VaccinationScheduleUpdate
from backend.app.api.deps import require_roles

router = APIRouter(prefix="/vaccines", tags=["Universal Immunization Schedule"])


@router.get("", response_model=List[VaccinationScheduleResponse])
@router.get("/", response_model=List[VaccinationScheduleResponse])
def get_all_vaccines(
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """
    Returns the National Universal Immunization Programme (UIP) master schedule.
    Vaccination schedule is stored in the database — not hard-coded in frontend.
    Pass include_inactive=true to see deactivated entries (admin use).
    """
    q = db.query(VaccinationSchedule)
    if not include_inactive:
        q = q.filter(VaccinationSchedule.is_active == True)
    return q.order_by(VaccinationSchedule.order_index, VaccinationSchedule.recommended_age_days).all()


@router.post("", response_model=VaccinationScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_vaccine_schedule(
    vac_in: VaccinationScheduleCreate,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Adds a new vaccine to the National UIP master schedule.
    """
    existing = db.query(VaccinationSchedule).filter(
        (VaccinationSchedule.vaccine_name == vac_in.vaccine_name) | (VaccinationSchedule.code == vac_in.code)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vaccine name or code already exists in master schedule."
        )

    new_vac = VaccinationSchedule(**vac_in.model_dump())
    db.add(new_vac)

    audit = AuditLog(
        user_id=current_user.id,
        action="VACCINE_SCHEDULE_CREATED",
        entity_type="VaccinationSchedule",
        entity_id=None,
        details=f"Added vaccine {new_vac.vaccine_name} ({new_vac.code}) to master schedule."
    )
    db.add(audit)
    db.commit()
    db.refresh(new_vac)
    return new_vac


@router.put("/{vaccine_id}", response_model=VaccinationScheduleResponse)
def update_vaccine_schedule(
    vaccine_id: int,
    vac_in: VaccinationScheduleUpdate,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Updates vaccine dosage, timing, route, or name in the master schedule.
    Historical ChildVaccination records are NOT affected — only the schedule definition changes.
    """
    vac = db.query(VaccinationSchedule).filter(VaccinationSchedule.id == vaccine_id).first()
    if not vac:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vaccination schedule item not found.")

    update_data = vac_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vac, field, value)

    audit = AuditLog(
        user_id=current_user.id,
        action="VACCINE_SCHEDULE_UPDATED",
        entity_type="VaccinationSchedule",
        entity_id=vac.id,
        details=f"Updated vaccine schedule for {vac.vaccine_name} (ID {vac.id})."
    )
    db.add(audit)
    db.commit()
    db.refresh(vac)
    return vac


@router.put("/{vaccine_id}/deactivate", response_model=VaccinationScheduleResponse)
def deactivate_vaccine_schedule(
    vaccine_id: int,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Soft-deactivates a vaccine entry. Historical ChildVaccination records
    are NEVER deleted — existing records are preserved. New children will not
    receive this vaccine in their generated schedule.
    """
    vac = db.query(VaccinationSchedule).filter(VaccinationSchedule.id == vaccine_id).first()
    if not vac:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vaccination schedule item not found.")

    vac.is_active = False
    audit = AuditLog(
        user_id=current_user.id,
        action="VACCINE_SCHEDULE_DEACTIVATED",
        entity_type="VaccinationSchedule",
        entity_id=vac.id,
        details=f"Deactivated vaccine {vac.vaccine_name} ({vac.code}). Historical child records preserved."
    )
    db.add(audit)
    db.commit()
    db.refresh(vac)
    return vac


@router.put("/{vaccine_id}/activate", response_model=VaccinationScheduleResponse)
def activate_vaccine_schedule(
    vaccine_id: int,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin: Re-activates a previously deactivated vaccine schedule entry.
    New children registered after re-activation will have this vaccine scheduled.
    """
    vac = db.query(VaccinationSchedule).filter(VaccinationSchedule.id == vaccine_id).first()
    if not vac:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vaccination schedule item not found.")

    vac.is_active = True
    audit = AuditLog(
        user_id=current_user.id,
        action="VACCINE_SCHEDULE_ACTIVATED",
        entity_type="VaccinationSchedule",
        entity_id=vac.id,
        details=f"Re-activated vaccine {vac.vaccine_name} ({vac.code})."
    )
    db.add(audit)
    db.commit()
    db.refresh(vac)
    return vac
