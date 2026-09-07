from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.models import Notification, User
from backend.app.schemas.schemas import NotificationResponse, NotificationCreate
from backend.app.api.deps import get_current_user, require_roles
from backend.app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
@router.get("/", response_model=List[NotificationResponse])
def get_user_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    priority: Optional[str] = Query(None, description="Filter by priority: HIGH, MEDIUM, LOW"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the authenticated user's in-app notification feed.
    """
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    if priority:
        query = query.filter(Notification.priority == priority.upper())

    if notification_type:
        query = query.filter(Notification.notification_type == notification_type)

    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return notifications


@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fast query for notification bell badge count.
    """
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    return {"unread_count": count}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marks a single notification as read.
    """
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found."
        )

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.post("/read-all")
def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marks all notifications for the current user as read.
    """
    updated_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True}, synchronize_session=False)

    db.commit()
    return {"message": f"Marked {updated_count} notifications as read.", "count": updated_count}


@router.post("/trigger-auto-generation")
def trigger_auto_notifications(
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Triggers automatic schedule scanning and generates targeted alerts
    for parents and ASHA workers based on dynamic UIP status.
    """
    summary = NotificationService.generate_automatic_vaccine_notifications(db)
    return {
        "status": "success",
        "summary": summary,
        "message": f"Generated {summary['total_generated']} notifications based on current UIP schedule."
    }


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_custom_notification(
    notif_in: NotificationCreate,
    current_user: User = Depends(require_roles(["asha", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Dispatches a custom notification. Restricted to ASHA/Admin: this lets a
    caller push a notification to an arbitrary user_id, so it must not be
    reachable by an ordinary parent account.
    """
    notif = NotificationService.send_notification(
        db=db,
        user_id=notif_in.user_id,
        title=notif_in.title,
        message=notif_in.message,
        notification_type=notif_in.notification_type,
        priority=notif_in.priority,
        channel=notif_in.channel,
        link=notif_in.link
    )
    return notif
