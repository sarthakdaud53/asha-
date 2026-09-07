from datetime import datetime, date, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Text,
    Index
)
from sqlalchemy.orm import relationship
from backend.app.db.database import Base

def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    """
    Core User entity for authentication, authorization, and base credentials.
    Separates security identity from role-specific domain models.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), nullable=True)
    password_hash = Column(String(255), nullable=False)
    password_reset_token_hash = Column(String(64), nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)
    role = Column(String(20), nullable=False, default="parent")  # 'parent', 'asha', 'admin'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # 1-to-1 Role Profile Relationships
    parent_profile = relationship("Parent", back_populates="user", uselist=False, cascade="all, delete-orphan")
    asha_profile = relationship("AshaWorker", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # User-level direct activities
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class Village(Base):
    """
    Rural administrative jurisdiction (Village, Sub-Center, PHC, Block, District).
    """
    __tablename__ = "villages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    sub_center = Column(String(100), nullable=False)
    phc_name = Column(String(100), nullable=False)  # Primary Health Centre
    district = Column(String(100), nullable=False)
    state = Column(String(100), default="Madhya Pradesh", nullable=False)
    pin_code = Column(String(10), nullable=True)
    population = Column(Integer, default=1500, nullable=False)
    location_village_id = Column(Integer, ForeignKey("location_villages.id", ondelete="RESTRICT"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    asha_workers = relationship("AshaWorker", back_populates="assigned_village", foreign_keys="AshaWorker.assigned_village_id")
    families = relationship("Family", back_populates="village")
    children = relationship("Child", back_populates="village")
    location_village = relationship("LocationVillage", back_populates="operational_villages")


class LocationState(Base):
    __tablename__ = "location_states"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    source = Column(String(120), nullable=False, default="LGD")
    source_version = Column(String(40), nullable=True)
    districts = relationship("LocationDistrict", back_populates="state", cascade="all, delete-orphan")


class LocationDistrict(Base):
    __tablename__ = "location_districts"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False, index=True)
    state_id = Column(Integer, ForeignKey("location_states.id", ondelete="CASCADE"), nullable=False, index=True)
    state = relationship("LocationState", back_populates="districts")
    subdistricts = relationship("LocationSubdistrict", back_populates="district", cascade="all, delete-orphan")


class LocationSubdistrict(Base):
    __tablename__ = "location_subdistricts"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False, index=True)
    district_id = Column(Integer, ForeignKey("location_districts.id", ondelete="CASCADE"), nullable=False, index=True)
    district = relationship("LocationDistrict", back_populates="subdistricts")
    villages = relationship("LocationVillage", back_populates="subdistrict", cascade="all, delete-orphan")


class LocationVillage(Base):
    __tablename__ = "location_villages"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(180), nullable=False, index=True)
    subdistrict_id = Column(Integer, ForeignKey("location_subdistricts.id", ondelete="CASCADE"), nullable=False, index=True)
    subdistrict = relationship("LocationSubdistrict", back_populates="villages")
    operational_villages = relationship("Village", back_populates="location_village")


class Parent(Base):
    """
    Parent Profile entity linked 1-to-1 with User.
    Contains family contact, socioeconomic and educational details.
    """
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    alternate_phone = Column(String(20), nullable=True)
    occupation = Column(String(100), nullable=True)
    education_level = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="parent_profile")
    families = relationship("Family", back_populates="parent", cascade="all, delete-orphan")
    children = relationship("Child", back_populates="parent", cascade="all, delete-orphan")


class AshaWorker(Base):
    """
    ASHA (Accredited Social Health Activist) Worker profile linked 1-to-1 with User.
    Tracks worker accreditation code, assigned village, qualification, and field activities.
    """
    __tablename__ = "asha_workers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    worker_code = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "ASHA-RAM-01"
    assigned_village_id = Column(Integer, ForeignKey("villages.id", ondelete="SET NULL"), nullable=True, index=True)
    qualification = Column(String(100), default="Higher Secondary (12th Pass)", nullable=True)
    experience_years = Column(Integer, default=3, nullable=False)
    joined_date = Column(Date, default=date.today, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="asha_profile")
    assigned_village = relationship("Village", back_populates="asha_workers", foreign_keys=[assigned_village_id])
    administered_vaccinations = relationship("ChildVaccination", back_populates="administered_by_asha")
    house_visits = relationship("HouseVisit", back_populates="asha_worker")
    verification_records = relationship("VerificationRecord", back_populates="verified_by_asha")


class AshaApplication(Base):
    __tablename__ = "asha_applications"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    username = Column(String(100), nullable=False, index=True)
    phone = Column(String(20), nullable=False, index=True)
    email = Column(String(150), nullable=True)
    location_village_id = Column(Integer, ForeignKey("location_villages.id", ondelete="RESTRICT"), nullable=False)
    qualification = Column(String(100), nullable=True)
    experience_years = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

class Family(Base):
    """
    Family / Household unit within a rural village.
    Links parents, ration card / socioeconomic status, and multiple children.
    """
    __tablename__ = "families"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True)
    village_id = Column(Integer, ForeignKey("villages.id", ondelete="RESTRICT"), nullable=False, index=True)
    family_head_name = Column(String(150), nullable=False)
    ration_card_number = Column(String(50), index=True, nullable=True)  # BPL / APL / Antyodaya
    house_number = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    contact_number = Column(String(20), nullable=True)
    socioeconomic_category = Column(String(50), default="BPL", nullable=False)  # BPL, APL, Antyodaya
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    parent = relationship("Parent", back_populates="families")
    village = relationship("Village", back_populates="families")
    children = relationship("Child", back_populates="family", cascade="all, delete-orphan")
    house_visits = relationship("HouseVisit", back_populates="family")


class Child(Base):
    """
    Child entity containing core demographics, health attributes,
    verification status, and family linkages.
    """
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True)
    village_id = Column(Integer, ForeignKey("villages.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Important Child Fields
    full_name = Column(String(150), nullable=False, index=True)
    date_of_birth = Column(Date, nullable=False, index=True)
    gender = Column(String(10), nullable=False)  # 'Male', 'Female', 'Other'
    birth_weight_kg = Column(Float, nullable=True)
    blood_group = Column(String(10), nullable=True)
    birth_place = Column(String(150), default="PHC", nullable=True)
    mother_name = Column(String(150), nullable=True)
    father_name = Column(String(150), nullable=True)
    rch_mcp_number = Column(String(50), unique=True, index=True, nullable=True)  # RCH/MCP Card Unique ID
    house_number = Column(String(50), nullable=True)
    parent_contact = Column(String(20), nullable=True)
    registration_date = Column(Date, default=date.today, nullable=False)
    verification_status = Column(String(20), default="pending", nullable=False)  # 'pending', 'verified', 'rejected'
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    family = relationship("Family", back_populates="children")
    parent = relationship("Parent", back_populates="children")
    village = relationship("Village", back_populates="children")
    vaccinations = relationship("ChildVaccination", back_populates="child", cascade="all, delete-orphan", order_by="ChildVaccination.scheduled_date")
    growth_records = relationship("GrowthRecord", back_populates="child", cascade="all, delete-orphan", order_by="GrowthRecord.recorded_date")
    house_visits = relationship("HouseVisit", back_populates="child", cascade="all, delete-orphan")
    verification_records = relationship("VerificationRecord", back_populates="child", cascade="all, delete-orphan")


class VaccinationSchedule(Base):
    """
    Universal Immunization Programme (UIP) Master Schedule.
    Stored centrally in the database and manageable by Admin.
    """
    __tablename__ = "vaccination_schedules"

    id = Column(Integer, primary_key=True, index=True)
    vaccine_name = Column(String(150), unique=True, nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "BCG", "PENTA_1"
    dose_number = Column(Integer, default=1, nullable=False)
    recommended_age_days = Column(Integer, nullable=False)  # Offset in days from child DOB
    recommended_timing = Column(String(50), nullable=False)  # e.g. "At Birth", "6 Weeks", "10 Weeks"
    category = Column(String(50), nullable=False)  # 'Birth', '6 Weeks', '10 Weeks', '14 Weeks', etc.
    min_gap_days = Column(Integer, default=0, nullable=False)
    dose_amount = Column(String(50), default="0.5 ml", nullable=False)
    route = Column(String(50), default="Intramuscular", nullable=False)
    site = Column(String(100), default="Left upper arm", nullable=False)
    prevents_diseases = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    child_vaccinations = relationship("ChildVaccination", back_populates="vaccination_schedule")


class ChildVaccination(Base):
    """
    Individual immunization record linking a Child with a VaccinationSchedule.
    Tracks dynamic status, dose administration, batch numbers, and AEFI adverse events.
    """
    __tablename__ = "child_vaccinations"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True)
    vaccination_schedule_id = Column(Integer, ForeignKey("vaccination_schedules.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(20), default="pending", index=True, nullable=False)  # 'pending', 'upcoming', 'due', 'overdue', 'administered', 'exempted'
    scheduled_date = Column(Date, nullable=False, index=True)
    administered_date = Column(Date, nullable=True)
    administered_by_asha_id = Column(Integer, ForeignKey("asha_workers.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_number = Column(String(50), nullable=True)
    session_site = Column(String(150), nullable=True)  # e.g. "Anganwadi Center 1"
    aefi_reported = Column(Boolean, default=False, nullable=False)
    aefi_details = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    child = relationship("Child", back_populates="vaccinations")
    vaccination_schedule = relationship("VaccinationSchedule", back_populates="child_vaccinations")
    administered_by_asha = relationship("AshaWorker", back_populates="administered_vaccinations")


class HouseVisit(Base):
    """
    ASHA worker door-to-door follow-up visits, counseling logs, and outreach records.
    Reduces unnecessary visits by tracking priority-targeted house visits.
    """
    __tablename__ = "house_visits"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=True, index=True)
    asha_worker_id = Column(Integer, ForeignKey("asha_workers.id", ondelete="CASCADE"), nullable=False, index=True)
    visit_date = Column(Date, nullable=False, index=True)
    reason = Column(String(200), nullable=False)  # 'Vaccination overdue', 'Vaccination follow-up', 'Information verification', 'Child information incomplete', 'Routine follow-up', 'Other authorized reason'
    priority = Column(String(20), default="MEDIUM", nullable=False)  # 'HIGH', 'MEDIUM', 'LOW'
    observations = Column(Text, nullable=True)
    remarks = Column(Text, nullable=False)
    action_taken = Column(String(200), nullable=True)
    next_visit_date = Column(Date, nullable=True)
    status = Column(String(20), default="scheduled", nullable=False)  # 'scheduled', 'completed', 'rescheduled', 'cancelled'
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    child = relationship("Child", back_populates="house_visits")
    family = relationship("Family", back_populates="house_visits")
    asha_worker = relationship("AshaWorker", back_populates="house_visits")


class VerificationRecord(Base):
    """
    Official verification audit record for newborn/child profiles verified by ASHA workers.
    """
    __tablename__ = "verification_records"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True)
    verified_by_asha_id = Column(Integer, ForeignKey("asha_workers.id", ondelete="CASCADE"), nullable=False, index=True)
    verification_date = Column(Date, default=date.today, nullable=False)
    status = Column(String(20), default="verified", nullable=False)  # 'verified', 'rejected', 'pending'
    remarks = Column(Text, nullable=True)
    documents_checked = Column(String(200), default="Birth Certificate / Hospital Discharge Card", nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    child = relationship("Child", back_populates="verification_records")
    verified_by_asha = relationship("AshaWorker", back_populates="verification_records")


class GrowthRecord(Base):
    """
    Periodic child growth monitoring (Weight, Height, MUAC) and WHO/IAP nutritional status.
    """
    __tablename__ = "growth_records"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_date = Column(Date, nullable=False, index=True)
    weight_kg = Column(Float, nullable=False)
    height_cm = Column(Float, nullable=True)
    muac_cm = Column(Float, nullable=True)  # Mid-Upper Arm Circumference
    nutritional_status = Column(String(50), default="Normal", nullable=False)  # 'Normal', 'MAM', 'SAM'
    recorded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    child = relationship("Child", back_populates="growth_records")
    recorded_by = relationship("User")


class Notification(Base):
    """
    In-app alerts, reminder queues, and notification dispatch logs.
    Structured for extensible in-app, SMS, WhatsApp, and Email delivery.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), default="due_reminder", nullable=False, index=True)  # 'vaccine_upcoming', 'vaccine_due', 'vaccine_overdue', 'verification_required', 'asha_followup', 'new_child_registration', 'parent_updated_info', 'priority_followup', 'general'
    priority = Column(String(20), default="MEDIUM", nullable=False)  # 'HIGH', 'MEDIUM', 'LOW'
    channel = Column(String(30), default="in_app", nullable=False)  # 'in_app', 'sms', 'whatsapp', 'email'
    link = Column(String(200), nullable=True)  # Deep link or reference ID (e.g. child ID)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    sent_at = Column(DateTime, default=utcnow, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    """
    System-wide audit trail recording critical actions, data changes, and admin operations.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # e.g., "CHILD_REGISTERED", "VACCINE_ADMINISTERED"
    entity_type = Column(String(50), nullable=False)  # "Child", "ChildVaccination", "Village"
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
