from typing import Generator, Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.core.security import decode_access_token
from backend.app.db.database import get_db
from backend.app.models.models import User, Child

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Authenticates user from JWT Bearer token.
    Raises 401 Unauthorized if missing, expired, or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Please contact your Health Center."
        )

    return user

def require_roles(allowed_roles: List[str]):
    """
    Role-Based Access Control dependency factory.
    Example: Depends(require_roles(["asha", "admin"]))
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}. Your role is '{current_user.role}'."
            )
        return current_user
    return role_checker

def validate_child_access(child_id: int, current_user: User, db: Session) -> Child:
    """
    Enforces strict role-based data isolation:
    - Parent: Can ONLY access children where Child.parent_id == current_user.parent_profile.id
    - ASHA Worker: Can ONLY access children where Child.village_id == current_user.asha_profile.assigned_village_id
    - Admin: Full access across all villages.
    """
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child record not found.")

    if current_user.role == "parent":
        if not current_user.parent_profile or child.parent_id != current_user.parent_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Parents can only access records for their own children."
            )
    elif current_user.role == "asha":
        if not current_user.asha_profile or child.village_id != current_user.asha_profile.assigned_village_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. ASHA workers can only access children in their assigned village jurisdiction."
            )

    return child
