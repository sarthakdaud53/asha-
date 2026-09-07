from typing import List, Optional
import hmac
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_password_reset_token,
    hash_password_reset_token,
    verify_password_reset_token
)
from backend.app.models.models import User, Village, Parent, AshaWorker, AshaApplication, Family, AuditLog, LocationVillage
from backend.app.schemas.schemas import (
    UserCreate,
    ParentRegistration,
    UserLogin,
    Token,
    UserResponse,
    VillageResponse,
    ForgotPasswordRequest,
    ResetPasswordConfirm,
    ChangePasswordRequest
    , AshaApplicationCreate, AshaApplicationResponse
)
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication & Password Recovery"])

@router.post("/asha-applications", response_model=AshaApplicationResponse, status_code=status.HTTP_201_CREATED)
def submit_asha_application(application: AshaApplicationCreate, db: Session = Depends(get_db)):
    if db.query(User).filter((User.username == application.username) | (User.phone == application.phone)).first():
        raise HTTPException(status_code=400, detail="Username or mobile number is already registered.")
    if db.query(AshaApplication).filter(
        ((AshaApplication.username == application.username) | (AshaApplication.phone == application.phone)) &
        (AshaApplication.status == "pending")
    ).first():
        raise HTTPException(status_code=400, detail="An application with these details is already pending.")
    location = db.query(LocationVillage).filter(LocationVillage.id == application.location_village_id).first()
    if not location or location.subdistrict_id != application.location_taluka_id or location.subdistrict.district_id != application.location_district_id or location.subdistrict.district.state_id != application.location_state_id:
        raise HTTPException(status_code=400, detail="Selected location hierarchy is inconsistent.")
    village = db.query(Village).filter(Village.location_village_id == location.id).first()
    if not village:
        raise HTTPException(status_code=400, detail="Selected village is not registered as an operational village yet.")
    user = User(
        username=application.username,
        phone=application.phone,
        full_name=application.full_name,
        email=application.email,
        password_hash=get_password_hash(application.password),
        role="asha",
        is_active=True,
    )
    db.add(user)
    db.flush()
    profile = AshaWorker(
        user_id=user.id,
        worker_code=f"ASHA-{village.name[:3].upper()}-{db.query(AshaWorker).count() + 1:02d}",
        assigned_village_id=village.id,
        qualification=application.qualification or "Higher Secondary",
        experience_years=application.experience_years,
        joined_date=date.today(),
    )
    db.add(profile)
    record = AshaApplication(
        full_name=application.full_name, username=application.username, phone=application.phone,
        email=application.email, location_village_id=location.id,
        qualification=application.qualification, experience_years=application.experience_years,
        status="approved",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return AshaApplicationResponse(
        id=record.id, full_name=record.full_name, username=record.username, phone=record.phone,
        email=record.email, location_village_id=location.id, village_name=location.name,
        status=record.status, qualification=record.qualification,
        experience_years=record.experience_years, created_at=record.created_at,
    )

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_parent(user_in: ParentRegistration, db: Session = Depends(get_db)):
    """
    Public self-registration flow for Parents using mobile number/email and password.
    Automatically establishes User, Parent, and Family records.
    """
    # Check if username or phone already exists
    existing_user = db.query(User).filter(
        (User.username == user_in.username) | (User.phone == user_in.phone)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or mobile phone number is already registered in the system."
        )

    village = db.query(Village).filter(Village.id == user_in.village_id).first() if user_in.village_id else None
    if user_in.location_village_id:
        location = db.query(LocationVillage).filter(LocationVillage.id == user_in.location_village_id).first()
        if not location:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected village does not exist.")
        if (user_in.location_taluka_id and location.subdistrict_id != user_in.location_taluka_id) or (
            user_in.location_district_id and location.subdistrict.district_id != user_in.location_district_id
        ) or (
            user_in.location_state_id and location.subdistrict.district.state_id != user_in.location_state_id
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
            detail="Selected village does not exist."
        )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        username=user_in.username,
        phone=user_in.phone,
        full_name=user_in.full_name,
        email=user_in.email,
        password_hash=hashed_pw,
        role="parent",
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create Parent Profile
    p_profile = Parent(
        user_id=new_user.id,
        alternate_phone=user_in.alternate_phone,
        occupation=user_in.occupation
    )
    db.add(p_profile)
    db.commit()
    db.refresh(p_profile)

    # Create Family Record
    fam = Family(
        parent_id=p_profile.id,
        village_id=village.id,
        family_head_name=new_user.full_name,
        house_number=user_in.address or "1",
        address=user_in.address or village.name,
        contact_number=new_user.phone
    )
    db.add(fam)
    
    # Audit log
    audit = AuditLog(
        user_id=new_user.id,
        action="PARENT_REGISTERED",
        entity_type="User",
        entity_id=new_user.id,
        details=f"Parent {new_user.full_name} registered in village {village.name}"
    )
    db.add(audit)
    db.commit()

    token_payload = {
        "sub": str(new_user.id),
        "username": new_user.username,
        "role": new_user.role,
        "full_name": new_user.full_name
    }
    access_token = create_access_token(token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=new_user.id,
        username=new_user.username,
        full_name=new_user.full_name,
        role=new_user.role,
        village_id=village.id,
        village_name=village.name
    )

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates user and returns JWT token with role context and village jurisdiction.
    """
    user = db.query(User).filter(
        (User.username == login_data.username) | (User.phone == login_data.username)
    ).first()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/mobile number or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Please contact your Primary Health Centre administrator."
        )

    village_id = None
    village_name = None

    if user.role == "parent" and user.parent_profile and user.parent_profile.families:
        fam = user.parent_profile.families[0]
        village_id = fam.village_id
        village_name = fam.village.name if fam.village else None
    elif user.role == "asha" and user.asha_profile and user.asha_profile.assigned_village:
        village_id = user.asha_profile.assigned_village_id
        village_name = user.asha_profile.assigned_village.name

    token_payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name
    }
    access_token = create_access_token(token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        village_id=village_id,
        village_name=village_name
    )

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Fetches the authenticated user profile with village and worker code details.
    """
    village_id = None
    village_name = None
    worker_code = None

    if current_user.role == "parent" and current_user.parent_profile and current_user.parent_profile.families:
        fam = current_user.parent_profile.families[0]
        village_id = fam.village_id
        village_name = fam.village.name if fam.village else None
    elif current_user.role == "asha" and current_user.asha_profile:
        worker_code = current_user.asha_profile.worker_code
        if current_user.asha_profile.assigned_village:
            village_id = current_user.asha_profile.assigned_village_id
            village_name = current_user.asha_profile.assigned_village.name

    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        phone=current_user.phone,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        village_id=village_id,
        village_name=village_name,
        worker_code=worker_code
    )

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Password reset initiation. Generates a secure reset token for recovery.
    """
    user = db.query(User).filter(
        (User.username == req.username_or_phone) | (User.phone == req.username_or_phone)
    ).first()

    if not user:
        # Avoid user enumeration in production, but provide clean message
        return {
            "message": "If an account matches the provided mobile/username, password reset instructions have been generated.",
            "reset_token": None
        }

    reset_token = create_password_reset_token(user.id, user.username)
    reset_payload = verify_password_reset_token(reset_token)
    if not reset_payload or not reset_payload.get("exp"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create password reset request."
        )
    user.password_reset_token_hash = hash_password_reset_token(reset_token)
    user.password_reset_expires_at = datetime.fromtimestamp(
        reset_payload["exp"], tz=timezone.utc
    )
    db.commit()

    # In development/debug mode return reset token for testing; in production do not expose it
    # In non-production environments (debug/test/etc.) return the reset token for automated tests and local debugging.
    if settings.APP_ENV.lower() != "production":
        return {
            "message": f"Password reset token generated successfully for {user.full_name}.",
            "reset_token": reset_token,
            "username": user.username,
            "phone": user.phone
        }

    # Production-safe response (avoid leaking tokens or confirming account existence)
    return {
        "message": "If an account matches the provided mobile/username, password reset instructions have been generated.",
        "reset_token": None
    }

@router.post("/reset-password")
def reset_password(req: ResetPasswordConfirm, db: Session = Depends(get_db)):
    """
    Completes password reset using verified reset token.
    """
    payload = verify_password_reset_token(req.token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )

    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    token_hash = hash_password_reset_token(req.token)
    expires_at = user.password_reset_expires_at
    if (
        not user.password_reset_token_hash
        or not hmac.compare_digest(user.password_reset_token_hash, token_hash)
        or (expires_at and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )

    user.password_hash = get_password_hash(req.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    
    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="PASSWORD_RESET",
        entity_type="User",
        entity_id=user.id,
        details=f"Password reset completed for user {user.username}"
    )
    db.add(audit)
    db.commit()

    return {"message": "Password has been successfully updated. You may now log in with your new password."}

@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authenticated password change requiring current password verification.
    """
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )

    current_user.password_hash = get_password_hash(req.new_password)
    
    audit = AuditLog(
        user_id=current_user.id,
        action="PASSWORD_CHANGED",
        entity_type="User",
        entity_id=current_user.id,
        details=f"User {current_user.username} updated password."
    )
    db.add(audit)
    db.commit()

    return {"message": "Password changed successfully."}

@router.get("/villages", response_model=List[VillageResponse])
def list_available_villages(db: Session = Depends(get_db)):
    """
    Returns list of villages for dropdowns and registrations.
    """
    villages = db.query(Village).order_by(Village.name).all()
    results = []
    for v in villages:
        asha_name = v.asha_workers[0].user.full_name if v.asha_workers and v.asha_workers[0].user else "Unassigned"
        results.append(VillageResponse(
            id=v.id,
            name=v.name,
            sub_center=v.sub_center,
            phc_name=v.phc_name,
            district=v.district,
            state=v.state,
            pin_code=v.pin_code,
            population=v.population,
            asha_worker_id=v.asha_workers[0].id if v.asha_workers else None,
            asha_worker_name=asha_name,
            created_at=v.created_at,
            total_children=len(v.children)
        ))
    return results
