from datetime import date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from backend.app.models.models import Child, VaccinationSchedule, ChildVaccination


class VaccineEngine:
    """
    UIP (Universal Immunization Programme) Dynamic Vaccination Tracking Engine.

    All vaccination schedules are fetched from the `vaccination_schedules` database table.
    The schedule is admin-configurable without code changes.
    Status values: upcoming | due | overdue | administered | not_applicable
    """

    # Status constants (used throughout system)
    STATUS_UPCOMING = "upcoming"
    STATUS_DUE = "due"
    STATUS_OVERDUE = "overdue"
    STATUS_ADMINISTERED = "administered"
    STATUS_NOT_APPLICABLE = "not_applicable"

    # Window thresholds (can be made admin-configurable later)
    DAYS_BEFORE_DUE = 14    # Show "due" this many days before scheduled date
    DAYS_GRACE_AFTER = 28   # Still show "due" (not overdue) within this window after date

    @staticmethod
    def generate_child_schedule(db: Session, child: Child) -> List[ChildVaccination]:
        """
        Creates all ChildVaccination records for a child based on:
        - Child's Date of Birth
        - Active VaccinationSchedule rows from database (NOT hardcoded)

        Called automatically on child registration.
        Must be re-called (with cleanup) if child DOB is corrected.
        """
        # Load master schedule from DB — admin can edit/add vaccines without code changes
        schedules = db.query(VaccinationSchedule).filter(
            VaccinationSchedule.is_active == True
        ).order_by(
            VaccinationSchedule.order_index,
            VaccinationSchedule.recommended_age_days
        ).all()

        created_records = []
        today = date.today()

        for sched in schedules:
            scheduled_date = child.date_of_birth + timedelta(days=sched.recommended_age_days)
            status = VaccineEngine._compute_status_from_date(scheduled_date, None, today)

            record = ChildVaccination(
                child_id=child.id,
                vaccination_schedule_id=sched.id,
                status=status,
                scheduled_date=scheduled_date,
                administered_date=None,
                batch_number=None,
                session_site=None,
                aefi_reported=False
            )
            db.add(record)
            created_records.append(record)

        db.flush()
        return created_records

    @staticmethod
    def _compute_status_from_date(
        scheduled_date: date,
        administered_date: Optional[date],
        current_date: Optional[date] = None
    ) -> str:
        """
        Core status calculation. Backend is authoritative — frontend never calculates status.

        Logic:
          - If administered_date is set → ADMINISTERED
          - If scheduled_date is far in future (>14 days) → UPCOMING
          - If within [-14, +28] window around scheduled_date → DUE
          - If more than 28 days past scheduled_date → OVERDUE
        """
        if administered_date is not None:
            return VaccineEngine.STATUS_ADMINISTERED

        if current_date is None:
            current_date = date.today()

        days_diff = (current_date - scheduled_date).days

        if days_diff < -VaccineEngine.DAYS_BEFORE_DUE:
            return VaccineEngine.STATUS_UPCOMING
        elif days_diff <= VaccineEngine.DAYS_GRACE_AFTER:
            return VaccineEngine.STATUS_DUE
        else:
            return VaccineEngine.STATUS_OVERDUE

    @staticmethod
    def compute_record_status(
        record: ChildVaccination,
        current_date: Optional[date] = None
    ) -> Tuple[str, int]:
        """
        Returns (status: str, days_overdue: int) for a single ChildVaccination record.
        Backend is the single source of truth for status — never trust frontend-derived status.
        """
        if current_date is None:
            current_date = date.today()

        status = VaccineEngine._compute_status_from_date(
            record.scheduled_date,
            record.administered_date,
            current_date
        )

        days_overdue = 0
        if status == VaccineEngine.STATUS_OVERDUE:
            days_overdue = (current_date - record.scheduled_date).days

        return status, days_overdue

    @staticmethod
    def compute_vaccination_timeline(
        child: Child,
        records: List[ChildVaccination],
        current_date: Optional[date] = None,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Computes a full vaccination timeline for a child, grouped by UIP category.
        status_filter: 'upcoming' | 'due' | 'overdue' | 'administered' | None (all)

        Returns list of enriched timeline entries ready for API/frontend rendering.
        """
        if current_date is None:
            current_date = date.today()

        timeline = []

        for rec in records:
            sched = rec.vaccination_schedule
            if not sched:
                continue

            status, days_overdue = VaccineEngine.compute_record_status(rec, current_date)

            # Apply filter if specified
            if status_filter and status_filter.lower() != "all":
                filter_map = {
                    "completed": "administered",
                    "not_applicable": "not_applicable"
                }
                mapped = filter_map.get(status_filter.lower(), status_filter.lower())
                if status != mapped:
                    continue

            # Scheduled date relative label
            scheduled_label = VaccineEngine._friendly_date(rec.scheduled_date)
            days_until = (rec.scheduled_date - current_date).days

            entry = {
                "record_id": rec.id,
                "vaccination_schedule_id": sched.id,
                "vaccine_name": sched.vaccine_name,
                "vaccine_code": sched.code,
                "dose_number": sched.dose_number,
                "category": sched.category,
                "recommended_timing": sched.recommended_timing,
                "dose_amount": sched.dose_amount,
                "route": sched.route,
                "site": sched.site,
                "prevents_diseases": sched.prevents_diseases,
                "description": sched.description or "",
                "order_index": sched.order_index,

                # Date information
                "scheduled_date": rec.scheduled_date.isoformat(),
                "scheduled_date_label": scheduled_label,
                "days_until": days_until,
                "days_overdue": days_overdue,

                # Status (backend-computed, not trusted from DB record cache)
                "status": status,
                "status_label": VaccineEngine._status_label(status, days_overdue),
                "urgency_score": VaccineEngine._urgency_score(status, days_overdue),

                # Completion info
                "administered_date": rec.administered_date.isoformat() if rec.administered_date else None,
                "administered_by_id": rec.administered_by_asha_id,
                "batch_number": rec.batch_number,
                "session_site": rec.session_site,
                "aefi_reported": rec.aefi_reported,
                "aefi_details": rec.aefi_details,
                "notes": rec.notes,

                # ASHA name (if available)
                "administered_by_name": (
                    rec.administered_by_asha.user.full_name
                    if rec.administered_by_asha and rec.administered_by_asha.user
                    else None
                )
            }
            timeline.append(entry)

        # Sort: overdue first, then due, then by scheduled date ascending
        timeline.sort(key=lambda x: (x["urgency_score"], x["scheduled_date"]))
        return timeline

    @staticmethod
    def calculate_child_metrics(
        child: Child,
        records: List[ChildVaccination],
        current_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculates summary KPI metrics for a child's immunization progress.
        Used on dashboard cards and child profile headers.
        """
        if current_date is None:
            current_date = date.today()

        total = len(records)
        completed = 0
        due = 0
        overdue = 0
        upcoming = 0
        overdue_vaccines = []
        due_vaccines = []
        next_due_date = None

        for rec in records:
            status, days_od = VaccineEngine.compute_record_status(rec, current_date)
            vac_name = rec.vaccination_schedule.vaccine_name if rec.vaccination_schedule else "Vaccine"

            if status == VaccineEngine.STATUS_ADMINISTERED:
                completed += 1
            elif status == VaccineEngine.STATUS_OVERDUE:
                overdue += 1
                overdue_vaccines.append({"name": vac_name, "days_overdue": days_od, "date": rec.scheduled_date.isoformat()})
            elif status == VaccineEngine.STATUS_DUE:
                due += 1
                due_vaccines.append({"name": vac_name, "date": rec.scheduled_date.isoformat()})
                if next_due_date is None or rec.scheduled_date < next_due_date:
                    next_due_date = rec.scheduled_date
            elif status == VaccineEngine.STATUS_UPCOMING:
                upcoming += 1
                if next_due_date is None or rec.scheduled_date < next_due_date:
                    next_due_date = rec.scheduled_date

        rate = round((completed / total * 100), 1) if total > 0 else 0.0
        has_alert = overdue > 0

        alert_summary = None
        if overdue > 0:
            names = ", ".join([v["name"] for v in overdue_vaccines[:2]])
            alert_summary = f"{overdue} Overdue: {names}"
            if overdue > 2:
                alert_summary += f" +{overdue - 2} more"

        return {
            "total_vaccines": total,
            "completed_vaccines": completed,
            "due_vaccines": due,
            "overdue_vaccines": overdue,
            "upcoming_vaccines": upcoming,
            "immunization_rate": rate,
            "has_alert": has_alert,
            "alert_summary": alert_summary,
            "age_formatted": VaccineEngine.format_child_age(child.date_of_birth, current_date),
            "next_due_date": next_due_date.isoformat() if next_due_date else None,
            "overdue_vaccine_list": overdue_vaccines,
            "due_vaccine_list": due_vaccines,
        }

    @staticmethod
    def _status_label(status: str, days_overdue: int) -> str:
        labels = {
            VaccineEngine.STATUS_UPCOMING: "Upcoming",
            VaccineEngine.STATUS_DUE: "Due Now",
            VaccineEngine.STATUS_OVERDUE: f"Overdue ({days_overdue}d)",
            VaccineEngine.STATUS_ADMINISTERED: "Completed",
            VaccineEngine.STATUS_NOT_APPLICABLE: "N/A",
        }
        return labels.get(status, status.capitalize())

    @staticmethod
    def _urgency_score(status: str, days_overdue: int) -> int:
        """Lower score = higher priority in sort order."""
        if status == VaccineEngine.STATUS_OVERDUE:
            return -days_overdue  # Most overdue first
        if status == VaccineEngine.STATUS_DUE:
            return 0
        if status == VaccineEngine.STATUS_UPCOMING:
            return 100
        if status == VaccineEngine.STATUS_ADMINISTERED:
            return 1000
        return 500

    @staticmethod
    def _friendly_date(d: date) -> str:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{d.day} {months[d.month - 1]} {d.year}"

    @staticmethod
    def format_child_age(dob: date, current_date: Optional[date] = None) -> str:
        """Formats age as human-readable string suitable for rural health cards."""
        if current_date is None:
            current_date = date.today()

        days = (current_date - dob).days
        if days < 0:
            return "Newborn"
        if days == 0:
            return "Born today"
        if days < 30:
            return f"{days} Day{'s' if days != 1 else ''}"

        months = days // 30
        remaining_days = days % 30

        if months < 12:
            if remaining_days > 5:
                return f"{months} Mo {remaining_days} D"
            return f"{months} Month{'s' if months != 1 else ''}"

        years = months // 12
        rem_months = months % 12
        if rem_months > 0:
            return f"{years} Yr {rem_months} Mo"
        return f"{years} Year{'s' if years != 1 else ''}"
