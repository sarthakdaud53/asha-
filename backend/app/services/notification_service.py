import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Notification, User, Child, ChildVaccination, Parent, AshaWorker, Village
)
from backend.app.services.vaccine_engine import VaccineEngine

logger = logging.getLogger("digital_asha.notifications")


class NotificationService:
    """
    Centralized Notification Engine for Digital ASHA.
    
    Features:
      - Multi-channel delivery architecture (In-App, SMS, WhatsApp, Email)
      - Automatic daily notification generation based on dynamic UIP status
      - Deduplication to avoid spamming parents/ASHA workers
      - Event-driven notifications (registration, updates, verification, house visits)
    """

    # Types
    TYPE_UPCOMING = "vaccine_upcoming"
    TYPE_DUE = "vaccine_due"
    TYPE_OVERDUE = "vaccine_overdue"
    TYPE_VERIFICATION = "verification_required"
    TYPE_ASHA_FOLLOWUP = "asha_followup"
    TYPE_NEW_REGISTRATION = "new_child_registration"
    TYPE_INFO_UPDATED = "parent_updated_info"
    TYPE_PRIORITY_FOLLOWUP = "priority_followup"
    TYPE_ADMINISTERED = "vaccine_administered"
    TYPE_GENERAL = "general"

    # Priorities
    PRIORITY_HIGH = "HIGH"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_LOW = "LOW"

    @staticmethod
    def send_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        notification_type: str = "general",
        priority: str = "MEDIUM",
        channel: str = "in_app",
        link: Optional[str] = None
    ) -> Notification:
        """
        Sends an in-app notification with deduplication and triggers external delivery channels.
        """
        # Deduplication check: Avoid inserting exact same unread notification on the same day
        today_start = datetime.combine(date.today(), datetime.min.time())
        existing = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.title == title,
            Notification.notification_type == notification_type,
            Notification.created_at >= today_start
        ).first()

        if existing:
            return existing

        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            channel=channel,
            link=link,
            is_read=False,
            sent_at=datetime.now(timezone.utc)
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        # Dispatch via multi-channel delivery stubs
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            NotificationService._dispatch_external_channels(user, title, message, channel)

        return notif

    @staticmethod
    def _dispatch_external_channels(user: User, title: str, message: str, channel: str):
        """
        Pluggable multi-channel delivery stub.
        Prepares SMS, WhatsApp, and Email payloads for telecom gateway integrations.
        """
        phone = user.phone
        email = user.email

        # 1. SMS Gateway dispatch stub
        if channel in ["sms", "all"] and phone:
            NotificationService._dispatch_sms(phone, f"[{title}] {message}")

        # 2. WhatsApp Business API dispatch stub
        if channel in ["whatsapp", "all"] and phone:
            NotificationService._dispatch_whatsapp(phone, message)

        # 3. Email Gateway dispatch stub
        if channel in ["email", "all"] and email:
            NotificationService._dispatch_email(email, title, message)

    @staticmethod
    def _dispatch_sms(phone: str, text: str):
        """Stub for NIC / DLT-compliant SMS Gateway (e.g. CDAC / Twilio)."""
        logger.info(f"[SMS DISPATCH STUB] To: {phone} | Text: {text}")

    @staticmethod
    def _dispatch_whatsapp(phone: str, text: str):
        """Stub for Meta WhatsApp Cloud API."""
        logger.info(f"[WHATSAPP DISPATCH STUB] To: {phone} | Message: {text}")

    @staticmethod
    def _dispatch_email(email: str, subject: str, body: str):
        """Stub for SMTP / SES Email service."""
        logger.info(f"[EMAIL DISPATCH STUB] To: {email} | Subject: {subject}")

    # ─── Event-Driven Notification Helpers ─────────────────────────────────────

    @staticmethod
    def notify_parent_vaccine_upcoming(db: Session, parent_user_id: int, child_name: str, vaccine_name: str, due_date: date, child_id: int):
        title = f"⏳ Upcoming Vaccine: {vaccine_name}"
        msg = f"Upcoming immunization '{vaccine_name}' for {child_name} is scheduled for {due_date.strftime('%d %b %Y')}. Please plan to visit your local Anganwadi/PHC."
        return NotificationService.send_notification(
            db=db,
            user_id=parent_user_id,
            title=title,
            message=msg,
            notification_type=NotificationService.TYPE_UPCOMING,
            priority=NotificationService.PRIORITY_MEDIUM,
            link=f"/parent.html?child_id={child_id}"
        )

    @staticmethod
    def notify_parent_vaccine_due(db: Session, parent_user_id: int, child_name: str, vaccine_name: str, due_date: date, child_id: int):
        title = f"🔔 Vaccination Due Now: {vaccine_name}"
        msg = f"{vaccine_name} for {child_name} is now DUE. Please bring your MCP card to the nearest Health Sub-Center."
        return NotificationService.send_notification(
            db=db,
            user_id=parent_user_id,
            title=title,
            message=msg,
            notification_type=NotificationService.TYPE_DUE,
            priority=NotificationService.PRIORITY_HIGH,
            link=f"/parent.html?child_id={child_id}"
        )

    @staticmethod
    def notify_parent_vaccine_overdue(db: Session, parent_user_id: int, child_name: str, vaccine_name: str, overdue_days: int, child_id: int):
        title = f"⚠️ URGENT: {vaccine_name} is Overdue"
        msg = f"Vaccination '{vaccine_name}' for {child_name} is {overdue_days} days overdue. Contact your ASHA worker immediately."
        return NotificationService.send_notification(
            db=db,
            user_id=parent_user_id,
            title=title,
            message=msg,
            notification_type=NotificationService.TYPE_OVERDUE,
            priority=NotificationService.PRIORITY_HIGH,
            link=f"/parent.html?child_id={child_id}"
        )

    @staticmethod
    def notify_parent_verification_needed(db: Session, parent_user_id: int, child_name: str, village_name: str, child_id: int):
        title = "📋 Information Verification Pending"
        msg = f"Your registration for {child_name} is awaiting field verification. Your assigned ASHA worker in {village_name} will visit shortly."
        return NotificationService.send_notification(
            db=db,
            user_id=parent_user_id,
            title=title,
            message=msg,
            notification_type=NotificationService.TYPE_VERIFICATION,
            priority=NotificationService.PRIORITY_MEDIUM,
            link=f"/parent.html?child_id={child_id}"
        )

    @staticmethod
    def notify_parent_asha_visit(db: Session, parent_user_id: int, child_name: str, asha_name: str, visit_date: date, reason: str):
        title = "🏡 Important ASHA Follow-up Visit"
        msg = f"ASHA worker {asha_name} has scheduled a home visit on {visit_date.strftime('%d %b %Y')} regarding: {reason}."
        return NotificationService.send_notification(
            db=db,
            user_id=parent_user_id,
            title=title,
            message=msg,
            notification_type=NotificationService.TYPE_ASHA_FOLLOWUP,
            priority=NotificationService.PRIORITY_HIGH
        )

    @staticmethod
    def notify_asha_new_registration(db: Session, asha_user_id: int, child_name: str, parent_name: str, village_name: str, child_id: int):
        title = f"👶 New Child Registered in {village_name}"
        msg = f"{parent_name} has registered newborn/child '{child_name}'. Please review and verify documents during your next visit."
        return NotificationService.send_notification(
            db=db,
            user_id=asha_user_id,
            title=title,
            message=msg,
            notification_type=NotificationService.TYPE_NEW_REGISTRATION,
            priority=NotificationService.PRIORITY_HIGH,
            link=f"/asha.html?child_id={child_id}"
        )

    @staticmethod
    def notify_asha_vaccine_overdue(db: Session, asha_user_id: int, child_name: str, vaccine_name: str, overdue_days: int, child_id: int):
        title = f"⚠️ Overdue Vaccine Alert: {child_name}"
        msg = f"{vaccine_name} for {child_name} is {overdue_days} days overdue. Added to your High-Priority Field Follow-up List."
        return NotificationService.send_notification(
            db=db,
            user_id=asha_user_id,
            title=title,
            message=msg,
            notification_type=NotificationService.TYPE_OVERDUE,
            priority=NotificationService.PRIORITY_HIGH,
            link=f"/asha.html?child_id={child_id}"
        )

    @staticmethod
    def notify_asha_info_updated(db: Session, asha_user_id: int, child_name: str, parent_name: str, child_id: int):
        title = f"✏️ Child Details Updated: {child_name}"
        msg = f"Parent {parent_name} updated information for {child_name}. Immunization schedule dates recalculated."
        return NotificationService.send_notification(
            db=db,
            user_id=asha_user_id,
            title=title,
            message=msg,
            notification_type=NotificationService.TYPE_INFO_UPDATED,
            priority=NotificationService.PRIORITY_MEDIUM,
            link=f"/asha.html?child_id={child_id}"
        )

    # ─── Automatic Schedule Evaluation Engine ─────────────────────────────────

    @staticmethod
    def generate_automatic_vaccine_notifications(db: Session) -> Dict[str, int]:
        """
        Evaluates dynamic vaccination schedules for all children and creates
        targeted in-app notifications for Parents and assigned ASHA workers.
        """
        today = date.today()
        children = db.query(Child).filter(Child.is_active == True).all()

        parent_notifs_count = 0
        asha_notifs_count = 0

        for c in children:
            parent_user = c.parent.user if c.parent and c.parent.user else None
            asha_user = None
            if c.village and c.village.asha_workers:
                asha = c.village.asha_workers[0]
                if asha.user:
                    asha_user = asha.user

            # 1. Check unverified registration
            if c.verification_status != "verified":
                if parent_user:
                    NotificationService.notify_parent_verification_needed(
                        db, parent_user.id, c.full_name, c.village.name if c.village else "Village", c.id
                    )
                    parent_notifs_count += 1
                if asha_user:
                    NotificationService.notify_asha_new_registration(
                        db, asha_user.id, c.full_name, parent_user.full_name if parent_user else "Parent", c.village.name if c.village else "Village", c.id
                    )
                    asha_notifs_count += 1

            # 2. Check each scheduled vaccination dose
            for rec in c.vaccinations:
                status, days_od = VaccineEngine.compute_record_status(rec, today)
                vac_name = rec.vaccination_schedule.vaccine_name if rec.vaccination_schedule else "Vaccine"

                if status == "overdue":
                    if parent_user:
                        NotificationService.notify_parent_vaccine_overdue(
                            db, parent_user.id, c.full_name, vac_name, days_od, c.id
                        )
                        parent_notifs_count += 1
                    if asha_user:
                        NotificationService.notify_asha_vaccine_overdue(
                            db, asha_user.id, c.full_name, vac_name, days_od, c.id
                        )
                        asha_notifs_count += 1

                elif status == "due":
                    if parent_user:
                        NotificationService.notify_parent_vaccine_due(
                            db, parent_user.id, c.full_name, vac_name, rec.scheduled_date, c.id
                        )
                        parent_notifs_count += 1

                elif status == "upcoming":
                    days_until = (rec.scheduled_date - today).days
                    if days_until <= 7 and parent_user:
                        NotificationService.notify_parent_vaccine_upcoming(
                            db, parent_user.id, c.full_name, vac_name, rec.scheduled_date, c.id
                        )
                        parent_notifs_count += 1

        return {
            "parent_notifications_generated": parent_notifs_count,
            "asha_notifications_generated": asha_notifs_count,
            "total_generated": parent_notifs_count + asha_notifs_count
        }
