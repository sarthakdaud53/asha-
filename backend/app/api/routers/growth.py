from typing import List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.models.models import GrowthRecord, Child, User
from backend.app.schemas.schemas import GrowthRecordCreate, GrowthRecordResponse
from backend.app.services.growth_service import GrowthService
from backend.app.services.notification_service import NotificationService
from backend.app.api.deps import get_current_user, require_roles, validate_child_access

router = APIRouter(prefix="/growth", tags=["Child Growth & Nutrition"])

@router.post("/{child_id}", response_model=GrowthRecordResponse, status_code=status.HTTP_201_CREATED)
def record_growth(
    child_id: int,
    growth_in: GrowthRecordCreate,
    current_user: User = Depends(require_roles(["asha", "admin", "parent"])),
    db: Session = Depends(get_db)
):
    """
    Records growth measurements and evaluates nutritional status (MAM/SAM).
    Enforces parent ownership / ASHA territory access.
    """
    child = validate_child_access(child_id, current_user, db)

    age_in_months = (growth_in.recorded_date - child.date_of_birth).days // 30

    nutritional_status = GrowthService.evaluate_nutrition(
        weight_kg=growth_in.weight_kg,
        height_cm=growth_in.height_cm,
        muac_cm=growth_in.muac_cm,
        age_in_months=age_in_months
    )

    new_record = GrowthRecord(
        child_id=child.id,
        recorded_date=growth_in.recorded_date,
        weight_kg=growth_in.weight_kg,
        height_cm=growth_in.height_cm,
        muac_cm=growth_in.muac_cm,
        nutritional_status=nutritional_status,
        recorded_by_id=current_user.id,
        notes=growth_in.notes
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    # Malnutrition alert
    if "SAM" in nutritional_status or "MAM" in nutritional_status:
        if child.parent and child.parent.user:
            NotificationService.send_notification(
                db=db,
                user_id=child.parent.user.id,
                title="⚠️ Nutrition Alert",
                message=f"{child.full_name}'s recent measurement indicates {nutritional_status}. Supplementary nutrition advised.",
                notification_type="growth_alert"
            )

    return GrowthRecordResponse(
        id=new_record.id,
        child_id=new_record.child_id,
        recorded_date=new_record.recorded_date,
        weight_kg=new_record.weight_kg,
        height_cm=new_record.height_cm,
        muac_cm=new_record.muac_cm,
        nutritional_status=new_record.nutritional_status,
        recorded_by_name=current_user.full_name,
        notes=new_record.notes,
        created_at=new_record.created_at
    )

@router.get("/child/{child_id}", response_model=List[GrowthRecordResponse])
def get_child_growth_history(
    child_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches historical growth records for a child with territory access validation.
    """
    child = validate_child_access(child_id, current_user, db)

    records = db.query(GrowthRecord).filter(
        GrowthRecord.child_id == child.id
    ).order_by(GrowthRecord.recorded_date.asc()).all()

    return [
        GrowthRecordResponse(
            id=r.id,
            child_id=r.child_id,
            recorded_date=r.recorded_date,
            weight_kg=r.weight_kg,
            height_cm=r.height_cm,
            muac_cm=r.muac_cm,
            nutritional_status=r.nutritional_status,
            recorded_by_name=r.recorded_by.full_name if r.recorded_by else "Health Worker",
            notes=r.notes,
            created_at=r.created_at
        )
        for r in records
    ]
