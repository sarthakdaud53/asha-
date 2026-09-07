from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# ----------------- Auth & User Schemas -----------------

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    phone: str = Field(..., min_length=10, max_length=15)
    full_name: str = Field(..., min_length=2, max_length=150)
    email: Optional[EmailStr] = None
    role: str = Field(default="parent")  # 'parent', 'asha', 'admin'
    is_active: bool = True

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)
    village_id: Optional[int] = None
    address: Optional[str] = None
    alternate_phone: Optional[str] = None
    occupation: Optional[str] = None

class ParentRegistration(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    phone: str = Field(..., min_length=10, max_length=15)
    full_name: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=6, max_length=100)
    email: Optional[EmailStr] = None
    village_id: Optional[int] = None
    location_state_id: Optional[int] = None
    location_district_id: Optional[int] = None
    location_taluka_id: Optional[int] = None
    location_village_id: Optional[int] = None
    address: Optional[str] = None
    alternate_phone: Optional[str] = None
    occupation: Optional[str] = None

class AshaWorkerCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    phone: str = Field(..., min_length=10, max_length=15)
    full_name: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=6, max_length=100)
    email: Optional[EmailStr] = None
    assigned_village_id: Optional[int] = None
    location_state_id: Optional[int] = None
    location_district_id: Optional[int] = None
    location_taluka_id: Optional[int] = None
    location_village_id: Optional[int] = None
    worker_code: Optional[str] = None
    qualification: Optional[str] = "Higher Secondary"
    experience_years: int = 1

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    full_name: str
    role: str
    village_id: Optional[int] = None
    village_name: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    village_id: Optional[int] = None
    village_name: Optional[str] = None
    worker_code: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# ----------------- Password Reset Schemas -----------------

class ForgotPasswordRequest(BaseModel):
    username_or_phone: str = Field(..., min_length=3)

class ResetPasswordConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=100)

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=100)

# ----------------- Parent & ASHA Profile Schemas -----------------

class ParentResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    phone: str
    alternate_phone: Optional[str] = None
    occupation: Optional[str] = None
    education_level: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AshaWorkerResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    phone: str
    email: Optional[str] = None
    worker_code: str
    assigned_village_id: Optional[int] = None
    assigned_village_name: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: int
    is_active: bool = True
    joined_date: date
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AshaApplicationCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    username: str = Field(..., min_length=3, max_length=50)
    phone: str = Field(..., min_length=10, max_length=15)
    email: Optional[EmailStr] = None
    location_state_id: int
    location_district_id: int
    location_taluka_id: int
    location_village_id: int
    qualification: Optional[str] = None
    experience_years: int = Field(0, ge=0, le=60)
    password: str = Field(..., min_length=6, max_length=100)

class AshaApplicationResponse(BaseModel):
    id: int
    full_name: str
    username: str
    phone: str
    email: Optional[str] = None
    location_village_id: int
    village_name: str
    status: str
    qualification: Optional[str] = None
    experience_years: int
    created_at: datetime
# ----------------- Village Schemas -----------------

class VillageBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    sub_center: str
    phc_name: str
    district: str
    state: str = "Madhya Pradesh"
    pin_code: Optional[str] = None
    population: int = 1500

class VillageCreate(VillageBase):
    location_village_id: Optional[int] = None

class VillageResponse(VillageBase):
    id: int
    created_at: datetime
    asha_worker_id: Optional[int] = None
    asha_worker_name: Optional[str] = None
    total_children: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)

# ----------------- Family Schemas -----------------

class FamilyBase(BaseModel):
    family_head_name: str
    ration_card_number: Optional[str] = None
    house_number: Optional[str] = None
    address: Optional[str] = None
    contact_number: Optional[str] = None
    socioeconomic_category: str = "BPL"

class FamilyCreate(FamilyBase):
    parent_id: int
    village_id: int

class FamilyResponse(FamilyBase):
    id: int
    parent_id: int
    village_id: int
    village_name: Optional[str] = None
    created_at: datetime
    total_children: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)

# ----------------- Vaccination Schedule Schemas -----------------

class VaccinationScheduleBase(BaseModel):
    vaccine_name: str
    code: str
    dose_number: int = 1
    recommended_age_days: int
    recommended_timing: str
    category: str
    min_gap_days: int = 0
    dose_amount: str = "0.5 ml"
    route: str = "Intramuscular"
    site: str = "Left upper arm"
    prevents_diseases: str
    description: Optional[str] = None
    is_active: bool = True
    order_index: int = 0

class VaccinationScheduleCreate(VaccinationScheduleBase):
    pass

class VaccinationScheduleUpdate(BaseModel):
    """Partial update schema — all fields optional for PATCH-like behavior."""
    vaccine_name: Optional[str] = None
    code: Optional[str] = None
    dose_number: Optional[int] = None
    recommended_age_days: Optional[int] = None
    recommended_timing: Optional[str] = None
    category: Optional[str] = None
    min_gap_days: Optional[int] = None
    dose_amount: Optional[str] = None
    route: Optional[str] = None
    site: Optional[str] = None
    prevents_diseases: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    order_index: Optional[int] = None

class VaccinationScheduleResponse(VaccinationScheduleBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

VaccineResponse = VaccinationScheduleResponse
VaccineCreate = VaccinationScheduleCreate

# ----------------- Child Vaccination Schemas -----------------

class ChildVaccinationBase(BaseModel):
    scheduled_date: date
    administered_date: Optional[date] = None
    batch_number: Optional[str] = None
    session_site: Optional[str] = None
    aefi_reported: bool = False
    aefi_details: Optional[str] = None
    notes: Optional[str] = None

class ChildVaccinationAdminister(BaseModel):
    administered_date: date
    batch_number: Optional[str] = "BATCH-2026"
    session_site: Optional[str] = "Anganwadi Center / PHC"
    aefi_reported: bool = False
    aefi_details: Optional[str] = None
    notes: Optional[str] = None

class ChildVaccinationResponse(BaseModel):
    id: int
    child_id: int
    vaccination_schedule_id: int
    vaccine_id: int
    vaccine_name: str
    vaccine_code: str
    category: str
    recommended_timing: str
    target_age_label: str
    route: str
    site: str
    dose_amount: str
    prevents_diseases: str
    status: str
    scheduled_date: date
    administered_date: Optional[date] = None
    administered_by_id: Optional[int] = None
    administered_by_name: Optional[str] = None
    batch_number: Optional[str] = None
    session_site: Optional[str] = None
    aefi_reported: bool = False
    aefi_details: Optional[str] = None
    notes: Optional[str] = None
    days_overdue: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)

ImmunizationRecordResponse = ChildVaccinationResponse
ImmunizationRecordAdminister = ChildVaccinationAdminister

# ----------------- Child Schemas -----------------

class ChildBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    date_of_birth: date
    gender: str = Field(..., pattern="^(Male|Female|Other)$")
    birth_weight_kg: Optional[float] = Field(None, ge=0.5, le=10.0)
    blood_group: Optional[str] = None
    birth_place: Optional[str] = "PHC"
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    rch_mcp_number: Optional[str] = None
    village_id: Optional[int] = None
    location_state_id: Optional[int] = None
    location_district_id: Optional[int] = None
    location_taluka_id: Optional[int] = None
    location_village_id: Optional[int] = None
    family_id: Optional[int] = None
    house_number: Optional[str] = None
    parent_contact: Optional[str] = None
    notes: Optional[str] = None

class ChildCreate(ChildBase):
    pass

class ChildUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    birth_weight_kg: Optional[float] = None
    blood_group: Optional[str] = None
    birth_place: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    rch_mcp_number: Optional[str] = None
    village_id: Optional[int] = None
    family_id: Optional[int] = None
    house_number: Optional[str] = None
    parent_contact: Optional[str] = None
    verification_status: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class ChildSummaryResponse(BaseModel):
    id: int
    parent_id: int
    family_id: Optional[int] = None
    parent_name: str
    parent_phone: str
    village_id: int
    village_name: str
    full_name: str
    date_of_birth: date
    age_formatted: str
    gender: str
    birth_weight_kg: Optional[float] = None
    blood_group: Optional[str] = None
    birth_place: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    rch_mcp_number: Optional[str] = None
    house_number: Optional[str] = None
    parent_contact: Optional[str] = None
    registration_date: date
    verification_status: str
    is_verified: bool
    is_active: bool
    created_at: datetime
    
    total_vaccines: int = 0
    completed_vaccines: int = 0
    due_vaccines: int = 0
    overdue_vaccines: int = 0
    upcoming_vaccines: int = 0
    immunization_rate: float = 0.0
    latest_nutritional_status: Optional[str] = "Normal"
    has_alert: bool = False
    alert_summary: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ChildDetailResponse(ChildSummaryResponse):
    immunizations: List[ChildVaccinationResponse] = []
    vaccinations: List[ChildVaccinationResponse] = []

# ----------------- House Visit Schemas -----------------

class HouseVisitCreate(BaseModel):
    child_id: int
    visit_date: date
    reason: str  # 'Vaccination overdue', 'Vaccination follow-up', 'Information verification', 'Child information incomplete', 'Routine follow-up', 'Other authorized reason'
    priority: Optional[str] = None  # 'HIGH', 'MEDIUM', 'LOW' (auto-calculated from reason if not provided)
    observations: Optional[str] = None
    remarks: Optional[str] = "Field visit scheduled"
    action_taken: Optional[str] = None
    next_visit_date: Optional[date] = None
    notes: Optional[str] = None
    status: str = "scheduled"

class HouseVisitReschedule(BaseModel):
    new_visit_date: date
    reason: Optional[str] = "Rescheduled due to family availability / session day"
    notes: Optional[str] = None

class HouseVisitComplete(BaseModel):
    observations: Optional[str] = None
    remarks: str
    action_taken: Optional[str] = None
    next_visit_date: Optional[date] = None
    notes: Optional[str] = None

class HouseVisitResponse(BaseModel):
    id: int
    child_id: int
    child_name: str
    family_id: Optional[int] = None
    family_head_name: Optional[str] = None
    house_number: Optional[str] = None
    parent_contact: Optional[str] = None
    asha_worker_id: int
    asha_name: str
    visit_date: date
    reason: str
    priority: str = "MEDIUM"
    observations: Optional[str] = None
    remarks: str
    action_taken: Optional[str] = None
    next_visit_date: Optional[date] = None
    status: str
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

FollowUpNoteCreate = HouseVisitCreate
FollowUpNoteResponse = HouseVisitResponse

# ----------------- Verification Record Schemas -----------------

class VerificationRecordCreate(BaseModel):
    child_id: int
    status: str = "verified"
    remarks: Optional[str] = None
    documents_checked: Optional[str] = "Birth Certificate / Hospital Card"

class VerificationRecordResponse(BaseModel):
    id: int
    child_id: int
    child_name: str
    verified_by_asha_id: int
    verified_by_name: str
    verification_date: date
    status: str
    remarks: Optional[str] = None
    documents_checked: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ----------------- Growth Schemas -----------------

class GrowthRecordCreate(BaseModel):
    recorded_date: date
    weight_kg: float = Field(..., gt=0.5, lt=80.0)
    height_cm: Optional[float] = Field(None, gt=20.0, lt=200.0)
    muac_cm: Optional[float] = Field(None, gt=5.0, lt=40.0)
    notes: Optional[str] = None

class GrowthRecordResponse(BaseModel):
    id: int
    child_id: int
    recorded_date: date
    weight_kg: float
    height_cm: Optional[float] = None
    muac_cm: Optional[float] = None
    nutritional_status: str
    recorded_by_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ----------------- Notification Schemas -----------------

class NotificationCreate(BaseModel):
    user_id: int
    title: str
    message: str
    notification_type: str = "general"  # 'vaccine_upcoming', 'vaccine_due', 'vaccine_overdue', 'verification_required', 'asha_followup', 'new_child_registration', 'parent_updated_info', 'priority_followup', 'general'
    priority: str = "MEDIUM"  # 'HIGH', 'MEDIUM', 'LOW'
    channel: str = "in_app"  # 'in_app', 'sms', 'whatsapp', 'email'
    link: Optional[str] = None

class NotificationResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    message: str
    notification_type: str
    priority: str = "MEDIUM"
    channel: str = "in_app"
    link: Optional[str] = None
    is_read: bool
    sent_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ----------------- Audit Log Schemas -----------------

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ----------------- Dashboard & Stats Schemas -----------------

class PriorityFollowUpItem(BaseModel):
    id: str
    child_id: int
    child_name: str
    age_formatted: str
    parent_name: str
    parent_phone: str
    village_name: str
    house_number: Optional[str] = "N/A"
    address: Optional[str] = "N/A"
    reason: str
    priority: str  # 'HIGH', 'MEDIUM', 'LOW'
    category_type: str  # 'overdue_vaccine', 'unverified_info', 'due_soon', 'incomplete_info', 'routine'
    due_date: str
    overdue_days: int = 0
    vaccine_names: List[str] = []
    whatsapp_message: str

class AshaDashboardStats(BaseModel):
    village_name: str
    sub_center: str
    phc_name: str
    total_families: int = 0
    total_children: int = 0
    total_registered_children: int = 0
    vaccinations_completed: int = 0
    vaccinations_due: int = 0
    vaccinations_overdue: int = 0
    upcoming_vaccinations: int = 0
    pending_verification: int = 0
    todays_followups: int = 0
    fully_immunized_children: int = 0
    partially_immunized_children: int = 0
    overdue_children_count: int = 0
    due_this_month_count: int = 0
    malnourished_children_count: int = 0
    coverage_percentage: float = 0.0
    unverified_registrations_count: int = 0

class AdminDashboardStats(BaseModel):
    total_villages: int
    total_asha_workers: int
    total_parents: int
    total_children: int
    total_vaccines_administered: int
    total_overdue_cases: int
    overall_immunization_rate: float
    villages_coverage: List[dict] = []
