import os
from datetime import date, timedelta, datetime, timezone
from sqlalchemy.orm import Session
from backend.app.db.database import SessionLocal, engine, Base
from backend.app.core.security import get_password_hash
from backend.app.models.models import (
    User,
    Village,
    Parent,
    AshaWorker,
    Family,
    Child,
    VaccinationSchedule,
    ChildVaccination,
    HouseVisit,
    VerificationRecord,
    GrowthRecord,
    Notification,
    AuditLog
)
from backend.app.services.vaccine_engine import VaccineEngine

# National UIP India Standard Vaccines
UIP_VACCINE_SCHEDULES = [
    # Birth
    {
        "vaccine_name": "BCG (Bacillus Calmette–Guérin)",
        "code": "BCG",
        "category": "Birth",
        "recommended_age_days": 0,
        "recommended_timing": "At Birth",
        "min_gap_days": 0,
        "dose_number": 1,
        "dose_amount": "0.1 ml",
        "route": "Intradermal",
        "site": "Left upper arm",
        "prevents_diseases": "Severe forms of childhood Tuberculosis (TB Meningitis & Miliary TB)",
        "description": "Administered at birth or within 1 year.",
        "is_active": True,
        "order_index": 1
    },
    {
        "vaccine_name": "OPV-0 (Oral Polio Vaccine Birth Dose)",
        "code": "OPV_0",
        "category": "Birth",
        "recommended_age_days": 0,
        "recommended_timing": "At Birth",
        "min_gap_days": 0,
        "dose_number": 1,
        "dose_amount": "2 drops",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Poliomyelitis",
        "description": "Birth dose within first 15 days.",
        "is_active": True,
        "order_index": 2
    },
    {
        "vaccine_name": "Hepatitis B - Birth Dose",
        "code": "HEPB_0",
        "category": "Birth",
        "recommended_age_days": 0,
        "recommended_timing": "At Birth",
        "min_gap_days": 0,
        "dose_number": 1,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Anterolateral aspect of mid-thigh (Left)",
        "prevents_diseases": "Hepatitis B virus infection / perinatal transmission",
        "description": "Must be given within 24 hours of birth.",
        "is_active": True,
        "order_index": 3
    },
    # 6 Weeks
    {
        "vaccine_name": "OPV-1 (Oral Polio Dose 1)",
        "code": "OPV_1",
        "category": "6 Weeks",
        "recommended_age_days": 42,
        "recommended_timing": "6 Weeks",
        "min_gap_days": 28,
        "dose_number": 1,
        "dose_amount": "2 drops",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Poliomyelitis",
        "description": "Primary series dose 1.",
        "is_active": True,
        "order_index": 4
    },
    {
        "vaccine_name": "Pentavalent-1 (DPT + HepB + Hib)",
        "code": "PENTA_1",
        "category": "6 Weeks",
        "recommended_age_days": 42,
        "recommended_timing": "6 Weeks",
        "min_gap_days": 28,
        "dose_number": 1,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Anterolateral aspect of mid-thigh (Left)",
        "prevents_diseases": "Diphtheria, Pertussis, Tetanus, Hepatitis B, Hib pneumonia/meningitis",
        "description": "5-in-1 combo vaccine dose 1.",
        "is_active": True,
        "order_index": 5
    },
    {
        "vaccine_name": "Rotavirus Vaccine-1 (RVV-1)",
        "code": "ROTA_1",
        "category": "6 Weeks",
        "recommended_age_days": 42,
        "recommended_timing": "6 Weeks",
        "min_gap_days": 28,
        "dose_number": 1,
        "dose_amount": "5 drops",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Severe rotaviral diarrhea and dehydration",
        "description": "Rotavirus liquid drops dose 1.",
        "is_active": True,
        "order_index": 6
    },
    {
        "vaccine_name": "fIPV-1 (Fractional Inactivated Polio Vaccine 1)",
        "code": "FIPV_1",
        "category": "6 Weeks",
        "recommended_age_days": 42,
        "recommended_timing": "6 Weeks",
        "min_gap_days": 28,
        "dose_number": 1,
        "dose_amount": "0.1 ml",
        "route": "Intradermal",
        "site": "Right upper arm",
        "prevents_diseases": "Poliomyelitis",
        "description": "Fractional IPV dose 1.",
        "is_active": True,
        "order_index": 7
    },
    {
        "vaccine_name": "PCV-1 (Pneumococcal Conjugate Vaccine 1)",
        "code": "PCV_1",
        "category": "6 Weeks",
        "recommended_age_days": 42,
        "recommended_timing": "6 Weeks",
        "min_gap_days": 28,
        "dose_number": 1,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Anterolateral aspect of mid-thigh (Right)",
        "prevents_diseases": "Pneumococcal pneumonia, sepsis and meningitis",
        "description": "Pneumococcal dose 1.",
        "is_active": True,
        "order_index": 8
    },
    # 10 Weeks
    {
        "vaccine_name": "OPV-2 (Oral Polio Dose 2)",
        "code": "OPV_2",
        "category": "10 Weeks",
        "recommended_age_days": 70,
        "recommended_timing": "10 Weeks",
        "min_gap_days": 28,
        "dose_number": 2,
        "dose_amount": "2 drops",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Poliomyelitis",
        "description": "Primary series dose 2.",
        "is_active": True,
        "order_index": 9
    },
    {
        "vaccine_name": "Pentavalent-2 (DPT + HepB + Hib)",
        "code": "PENTA_2",
        "category": "10 Weeks",
        "recommended_age_days": 70,
        "recommended_timing": "10 Weeks",
        "min_gap_days": 28,
        "dose_number": 2,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Anterolateral aspect of mid-thigh (Left)",
        "prevents_diseases": "Diphtheria, Pertussis, Tetanus, Hepatitis B, Hib",
        "description": "5-in-1 combo vaccine dose 2.",
        "is_active": True,
        "order_index": 10
    },
    {
        "vaccine_name": "Rotavirus Vaccine-2 (RVV-2)",
        "code": "ROTA_2",
        "category": "10 Weeks",
        "recommended_age_days": 70,
        "recommended_timing": "10 Weeks",
        "min_gap_days": 28,
        "dose_number": 2,
        "dose_amount": "5 drops",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Severe rotaviral diarrhea",
        "description": "Rotavirus liquid drops dose 2.",
        "is_active": True,
        "order_index": 11
    },
    # 14 Weeks
    {
        "vaccine_name": "OPV-3 (Oral Polio Dose 3)",
        "code": "OPV_3",
        "category": "14 Weeks",
        "recommended_age_days": 98,
        "recommended_timing": "14 Weeks",
        "min_gap_days": 28,
        "dose_number": 3,
        "dose_amount": "2 drops",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Poliomyelitis",
        "description": "Primary series dose 3.",
        "is_active": True,
        "order_index": 12
    },
    {
        "vaccine_name": "Pentavalent-3 (DPT + HepB + Hib)",
        "code": "PENTA_3",
        "category": "14 Weeks",
        "recommended_age_days": 98,
        "recommended_timing": "14 Weeks",
        "min_gap_days": 28,
        "dose_number": 3,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Anterolateral aspect of mid-thigh (Left)",
        "prevents_diseases": "Diphtheria, Pertussis, Tetanus, Hepatitis B, Hib",
        "description": "5-in-1 combo vaccine dose 3.",
        "is_active": True,
        "order_index": 13
    },
    {
        "vaccine_name": "Rotavirus Vaccine-3 (RVV-3)",
        "code": "ROTA_3",
        "category": "14 Weeks",
        "recommended_age_days": 98,
        "recommended_timing": "14 Weeks",
        "min_gap_days": 28,
        "dose_number": 3,
        "dose_amount": "5 drops",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Severe rotaviral diarrhea",
        "description": "Rotavirus liquid drops dose 3.",
        "is_active": True,
        "order_index": 14
    },
    {
        "vaccine_name": "fIPV-2 (Fractional Inactivated Polio Vaccine 2)",
        "code": "FIPV_2",
        "category": "14 Weeks",
        "recommended_age_days": 98,
        "recommended_timing": "14 Weeks",
        "min_gap_days": 28,
        "dose_number": 2,
        "dose_amount": "0.1 ml",
        "route": "Intradermal",
        "site": "Right upper arm",
        "prevents_diseases": "Poliomyelitis",
        "description": "Fractional IPV dose 2.",
        "is_active": True,
        "order_index": 15
    },
    {
        "vaccine_name": "PCV-2 (Pneumococcal Conjugate Vaccine 2)",
        "code": "PCV_2",
        "category": "14 Weeks",
        "recommended_age_days": 98,
        "recommended_timing": "14 Weeks",
        "min_gap_days": 28,
        "dose_number": 2,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Anterolateral aspect of mid-thigh (Right)",
        "prevents_diseases": "Pneumococcal pneumonia and meningitis",
        "description": "Pneumococcal dose 2.",
        "is_active": True,
        "order_index": 16
    },
    # 9-12 Months
    {
        "vaccine_name": "MR-1 (Measles & Rubella 1st Dose)",
        "code": "MR_1",
        "category": "9-12 Months",
        "recommended_age_days": 270,
        "recommended_timing": "9-12 Months",
        "min_gap_days": 0,
        "dose_number": 1,
        "dose_amount": "0.5 ml",
        "route": "Subcutaneous",
        "site": "Right upper arm",
        "prevents_diseases": "Measles and Congenital Rubella Syndrome",
        "description": "First dose of MR at 9 completed months.",
        "is_active": True,
        "order_index": 17
    },
    {
        "vaccine_name": "JE-1 (Japanese Encephalitis 1st Dose)",
        "code": "JE_1",
        "category": "9-12 Months",
        "recommended_age_days": 270,
        "recommended_timing": "9-12 Months",
        "min_gap_days": 0,
        "dose_number": 1,
        "dose_amount": "0.5 ml",
        "route": "Subcutaneous",
        "site": "Left upper arm",
        "prevents_diseases": "Japanese Encephalitis (Brain fever)",
        "description": "In endemic districts.",
        "is_active": True,
        "order_index": 18
    },
    {
        "vaccine_name": "PCV Booster",
        "code": "PCV_BOOSTER",
        "category": "9-12 Months",
        "recommended_age_days": 270,
        "recommended_timing": "9 Months",
        "min_gap_days": 0,
        "dose_number": 3,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Anterolateral aspect of mid-thigh (Right)",
        "prevents_diseases": "Pneumococcal disease booster protection",
        "description": "Booster dose at 9 months.",
        "is_active": True,
        "order_index": 19
    },
    {
        "vaccine_name": "Vitamin A (1st Dose)",
        "code": "VIT_A_1",
        "category": "9-12 Months",
        "recommended_age_days": 270,
        "recommended_timing": "9 Months",
        "min_gap_days": 0,
        "dose_number": 1,
        "dose_amount": "1 ml (1 lakh IU)",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Night blindness and childhood morbidity",
        "description": "Given along with MR-1 at 9 months.",
        "is_active": True,
        "order_index": 20
    },
    # 16-24 Months
    {
        "vaccine_name": "MR-2 (Measles & Rubella 2nd Dose)",
        "code": "MR_2",
        "category": "16-24 Months",
        "recommended_age_days": 480,
        "recommended_timing": "16-24 Months",
        "min_gap_days": 0,
        "dose_number": 2,
        "dose_amount": "0.5 ml",
        "route": "Subcutaneous",
        "site": "Right upper arm",
        "prevents_diseases": "Measles and Rubella booster immunity",
        "description": "Second dose at 16-24 months.",
        "is_active": True,
        "order_index": 21
    },
    {
        "vaccine_name": "DPT Booster-1",
        "code": "DPT_B1",
        "category": "16-24 Months",
        "recommended_age_days": 480,
        "recommended_timing": "16-24 Months",
        "min_gap_days": 0,
        "dose_number": 4,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Anterolateral aspect of mid-thigh (Left)",
        "prevents_diseases": "Diphtheria, Pertussis (Whooping Cough), Tetanus",
        "description": "First booster dose of DPT.",
        "is_active": True,
        "order_index": 22
    },
    {
        "vaccine_name": "OPV Booster",
        "code": "OPV_BOOSTER",
        "category": "16-24 Months",
        "recommended_age_days": 480,
        "recommended_timing": "16-24 Months",
        "min_gap_days": 0,
        "dose_number": 4,
        "dose_amount": "2 drops",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Poliomyelitis booster",
        "description": "Oral polio booster.",
        "is_active": True,
        "order_index": 23
    },
    {
        "vaccine_name": "Vitamin A (2nd Dose)",
        "code": "VIT_A_2",
        "category": "16-24 Months",
        "recommended_age_days": 480,
        "recommended_timing": "16-24 Months",
        "min_gap_days": 180,
        "dose_number": 2,
        "dose_amount": "2 ml (2 lakh IU)",
        "route": "Oral",
        "site": "Oral",
        "prevents_diseases": "Vitamin A deficiency and ocular health",
        "description": "Biannual dose 2.",
        "is_active": True,
        "order_index": 24
    },
    # 5-6 Years
    {
        "vaccine_name": "DPT Booster-2",
        "code": "DPT_B2",
        "category": "5-6 Years",
        "recommended_age_days": 1825,
        "recommended_timing": "5-6 Years",
        "min_gap_days": 0,
        "dose_number": 5,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Left upper arm",
        "prevents_diseases": "Diphtheria, Pertussis, Tetanus school-age booster",
        "description": "Second DPT booster dose.",
        "is_active": True,
        "order_index": 25
    },
    # 10 & 16 Years
    {
        "vaccine_name": "Td (Tetanus & adult Diphtheria 10 Yrs)",
        "code": "TD_10Y",
        "category": "10 Years",
        "recommended_age_days": 3650,
        "recommended_timing": "10 Years",
        "min_gap_days": 0,
        "dose_number": 1,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Upper arm",
        "prevents_diseases": "Tetanus and Diphtheria in adolescents",
        "description": "Adolescent Td dose at 10 years.",
        "is_active": True,
        "order_index": 26
    },
    {
        "vaccine_name": "Td (Tetanus & adult Diphtheria 16 Yrs)",
        "code": "TD_16Y",
        "category": "16 Years",
        "recommended_age_days": 5840,
        "recommended_timing": "16 Years",
        "min_gap_days": 0,
        "dose_number": 2,
        "dose_amount": "0.5 ml",
        "route": "Intramuscular",
        "site": "Upper arm",
        "prevents_diseases": "Tetanus and Diphtheria in late adolescents",
        "description": "Adolescent Td dose at 16 years.",
        "is_active": True,
        "order_index": 27
    }
]

def seed_database(db: Session = None):
    """
    Seeds database with normalized tables:
    VaccinationSchedules, Villages, Users, Parents, AshaWorkers,
    Families, Children, ChildVaccinations, HouseVisits, VerificationRecords,
    GrowthRecords, Notifications, and AuditLogs.
    """
    close_at_end = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        close_at_end = True

    try:
        # 1. Seed Master UIP Vaccination Schedules
        existing_schedules = db.query(VaccinationSchedule).count()
        if existing_schedules == 0:
            print("[SEED] Seeding National UIP Vaccination Schedules...")
            for s_data in UIP_VACCINE_SCHEDULES:
                sched = VaccinationSchedule(**s_data)
                db.add(sched)
            db.commit()
            print(f"[SEED] Seeded {len(UIP_VACCINE_SCHEDULES)} UIP vaccination schedules.")

        # 2. Seed Rural Villages
        if db.query(Village).count() == 0:
            print("[SEED] Seeding Rural Villages & Health Centers...")
            v1 = Village(
                name="Rampur",
                sub_center="Rampur Sub-Center",
                phc_name="Rampur Primary Health Centre",
                district="Sehore",
                state="Madhya Pradesh",
                pin_code="466001",
                population=1850
            )
            v2 = Village(
                name="Belur",
                sub_center="Belur Sub-Center",
                phc_name="Rampur Primary Health Centre",
                district="Sehore",
                state="Madhya Pradesh",
                pin_code="466002",
                population=1420
            )
            v3 = Village(
                name="Chandpur",
                sub_center="Chandpur Sub-Center",
                phc_name="Ashta Community Health Centre",
                district="Sehore",
                state="Madhya Pradesh",
                pin_code="466116",
                population=2100
            )
            v4 = Village(
                name="Shivpuri Rural",
                sub_center="Shivpuri Sub-Center",
                phc_name="Ashta Community Health Centre",
                district="Sehore",
                state="Madhya Pradesh",
                pin_code="466118",
                population=980
            )
            db.add_all([v1, v2, v3, v4])
            db.commit()

        v_rampur = db.query(Village).filter(Village.name == "Rampur").first()
        v_belur = db.query(Village).filter(Village.name == "Belur").first()

        # 3. Seed Users, Parents, and AshaWorkers
        if db.query(User).count() == 0:
            print("[SEED] Seeding Users, Parents, and ASHA Workers...")
            # Admin User
            admin_u = User(
                username="admin",
                phone="9876500000",
                full_name="Dr. Rajesh Sharma",
                email="admin@digitalasha.gov.in",
                password_hash=get_password_hash("admin123"),
                role="admin",
                is_active=True
            )
            db.add(admin_u)
            db.commit()

            # ASHA Worker 1: Sunita Devi (Rampur)
            asha1_u = User(
                username="asha_sunita",
                phone="9876511111",
                full_name="Sunita Devi (ASHA)",
                email="sunita.asha@digitalasha.gov.in",
                password_hash=get_password_hash("asha123"),
                role="asha",
                is_active=True
            )
            db.add(asha1_u)
            db.commit()

            asha1_profile = AshaWorker(
                user_id=asha1_u.id,
                worker_code="ASHA-RAM-01",
                assigned_village_id=v_rampur.id,
                qualification="Higher Secondary (12th Pass)",
                experience_years=4,
                joined_date=date.today() - timedelta(days=1400)
            )
            db.add(asha1_profile)
            db.commit()

            # ASHA Worker 2: Rekha Bai (Belur)
            asha2_u = User(
                username="asha_rekha",
                phone="9876522222",
                full_name="Rekha Bai (ASHA)",
                email="rekha.asha@digitalasha.gov.in",
                password_hash=get_password_hash("asha123"),
                role="asha",
                is_active=True
            )
            db.add(asha2_u)
            db.commit()

            asha2_profile = AshaWorker(
                user_id=asha2_u.id,
                worker_code="ASHA-BEL-02",
                assigned_village_id=v_belur.id,
                qualification="ANM Nursing Diploma",
                experience_years=6,
                joined_date=date.today() - timedelta(days=2100)
            )
            db.add(asha2_profile)
            db.commit()

            # Parents
            # Parent 1: Priya Kumari
            p1_u = User(
                username="parent_priya",
                phone="9876533333",
                full_name="Priya Kumari",
                email="priya@example.com",
                password_hash=get_password_hash("parent123"),
                role="parent",
                is_active=True
            )
            db.add(p1_u)
            db.commit()

            p1_profile = Parent(
                user_id=p1_u.id,
                alternate_phone="9876533334",
                occupation="Homemaker",
                education_level="Graduate (B.A.)"
            )
            db.add(p1_profile)
            db.commit()

            # Family 1 for Priya
            f1 = Family(
                parent_id=p1_profile.id,
                village_id=v_rampur.id,
                family_head_name="Ramesh Kumar",
                ration_card_number="BPL-RAM-2024-819",
                house_number="12",
                address="House 12, Main Street, Rampur",
                contact_number="9876533333",
                socioeconomic_category="BPL"
            )
            db.add(f1)
            db.commit()

            # Parent 2: Anita Sharma
            p2_u = User(
                username="parent_anita",
                phone="9876544444",
                full_name="Anita Sharma",
                email="anita@example.com",
                password_hash=get_password_hash("parent123"),
                role="parent",
                is_active=True
            )
            db.add(p2_u)
            db.commit()

            p2_profile = Parent(
                user_id=p2_u.id,
                alternate_phone="9876544445",
                occupation="Self-Employed / Tailor",
                education_level="10th Pass"
            )
            db.add(p2_profile)
            db.commit()

            # Family 2 for Anita
            f2 = Family(
                parent_id=p2_profile.id,
                village_id=v_rampur.id,
                family_head_name="Suresh Sharma",
                ration_card_number="BPL-RAM-2023-452",
                house_number="58",
                address="House 58, Near Panchayat Bhawan, Rampur",
                contact_number="9876544444",
                socioeconomic_category="BPL"
            )
            db.add(f2)
            db.commit()

            # Parent 3: Radha Patel
            p3_u = User(
                username="parent_radha",
                phone="9876555555",
                full_name="Radha Patel",
                email="radha@example.com",
                password_hash=get_password_hash("parent123"),
                role="parent",
                is_active=True
            )
            db.add(p3_u)
            db.commit()

            p3_profile = Parent(
                user_id=p3_u.id,
                alternate_phone="9876555556",
                occupation="Farmer",
                education_level="8th Pass"
            )
            db.add(p3_profile)
            db.commit()

            # Family 3 for Radha
            f3 = Family(
                parent_id=p3_profile.id,
                village_id=v_belur.id,
                family_head_name="Dinesh Patel",
                ration_card_number="APL-BEL-2022-109",
                house_number="19",
                address="House 19, Belur",
                contact_number="9876555555",
                socioeconomic_category="APL"
            )
            db.add(f3)
            db.commit()

            # 4. Seed Children
            print("[SEED] Seeding Children and Generating ChildVaccination schedules...")
            today = date.today()

            # Child 1: Aarav Kumar (Born 60 days ago) -> Parent: Priya
            c1 = Child(
                parent_id=p1_profile.id,
                family_id=f1.id,
                village_id=v_rampur.id,
                full_name="Aarav Kumar",
                date_of_birth=today - timedelta(days=60),
                gender="Male",
                birth_weight_kg=3.1,
                blood_group="B+",
                birth_place="Rampur PHC",
                mother_name="Priya Kumari",
                father_name="Ramesh Kumar",
                rch_mcp_number="RCH-RAM-2026-0012",
                house_number="12",
                parent_contact="9876533333",
                registration_date=today - timedelta(days=58),
                verification_status="verified",
                is_active=True
            )
            db.add(c1)
            db.commit()
            VaccineEngine.generate_child_schedule(db, c1)

            # Mark Birth vaccines as given for Aarav
            for cv in c1.vaccinations:
                if cv.vaccination_schedule.category == "Birth":
                    cv.administered_date = c1.date_of_birth
                    cv.status = "administered"
                    cv.administered_by_asha_id = asha1_profile.id
                    cv.batch_number = "VAC-2026-B101"
                    cv.session_site = "Rampur PHC Labour Room"

            # Verification record for Aarav
            vr1 = VerificationRecord(
                child_id=c1.id,
                verified_by_asha_id=asha1_profile.id,
                verification_date=today - timedelta(days=55),
                status="verified",
                remarks="Verified during first home visit. Birth certificate checked.",
                documents_checked="PHC Birth Certificate & MCP Card"
            )
            db.add(vr1)

            # Growth records for Aarav
            g1_1 = GrowthRecord(
                child_id=c1.id,
                recorded_date=c1.date_of_birth,
                weight_kg=3.1,
                height_cm=49.0,
                muac_cm=11.8,
                nutritional_status="Normal",
                recorded_by_id=asha1_u.id,
                notes="Healthy newborn birth weight"
            )
            g1_2 = GrowthRecord(
                child_id=c1.id,
                recorded_date=today - timedelta(days=15),
                weight_kg=4.8,
                height_cm=56.0,
                muac_cm=13.0,
                nutritional_status="Normal",
                recorded_by_id=asha1_u.id,
                notes="Good weight gain"
            )
            db.add_all([g1_1, g1_2])

            # Child 2: Ananya Sharma (Born 210 days ago) -> Parent: Anita (Overdue doses)
            c2 = Child(
                parent_id=p2_profile.id,
                family_id=f2.id,
                village_id=v_rampur.id,
                full_name="Ananya Sharma",
                date_of_birth=today - timedelta(days=210),
                gender="Female",
                birth_weight_kg=2.8,
                blood_group="O+",
                birth_place="District Hospital Sehore",
                mother_name="Anita Sharma",
                father_name="Suresh Sharma",
                rch_mcp_number="RCH-RAM-2025-0842",
                house_number="58",
                parent_contact="9876544444",
                registration_date=today - timedelta(days=205),
                verification_status="verified",
                is_active=True
            )
            db.add(c2)
            db.commit()
            VaccineEngine.generate_child_schedule(db, c2)

            # Administer only Birth & 6w doses for Ananya
            for cv in c2.vaccinations:
                if cv.vaccination_schedule.category in ["Birth", "6 Weeks"]:
                    cv.administered_date = c2.date_of_birth + timedelta(days=cv.vaccination_schedule.recommended_age_days)
                    cv.status = "administered"
                    cv.administered_by_asha_id = asha1_profile.id
                    cv.batch_number = "VAC-2025-P204"
                    cv.session_site = "Anganwadi Center 2, Rampur"

            # House visit for Ananya
            hv2 = HouseVisit(
                child_id=c2.id,
                family_id=f2.id,
                asha_worker_id=asha1_profile.id,
                visit_date=today - timedelta(days=5),
                reason="Overdue Pentavalent-2 & Pentavalent-3 Follow-up",
                observations="Child active but slightly underweight. Mother was out of station.",
                remarks="Counselled mother on completing missed doses at next village session.",
                action_taken="Scheduled attendance at upcoming Wednesday Sub-Center session.",
                next_visit_date=today + timedelta(days=7),
                status="completed"
            )
            db.add(hv2)

            # Growth record for Ananya with MAM
            g2 = GrowthRecord(
                child_id=c2.id,
                recorded_date=today - timedelta(days=5),
                weight_kg=5.9,
                height_cm=62.0,
                muac_cm=12.1,
                nutritional_status="MAM - Moderate Acute Malnutrition",
                recorded_by_id=asha1_u.id,
                notes="Moderate underweight. Supplementary nutrition THR advised."
            )
            db.add(g2)

            # Child 3: Vihaan Patel (Born 540 days ago) -> Parent: Radha (Belur)
            c3 = Child(
                parent_id=p3_profile.id,
                family_id=f3.id,
                village_id=v_belur.id,
                full_name="Vihaan Patel",
                date_of_birth=today - timedelta(days=540),
                gender="Male",
                birth_weight_kg=3.3,
                blood_group="A+",
                birth_place="Belur Sub-Center",
                mother_name="Radha Patel",
                father_name="Dinesh Patel",
                rch_mcp_number="RCH-BEL-2025-0104",
                house_number="19",
                parent_contact="9876555555",
                registration_date=today - timedelta(days=530),
                verification_status="verified",
                is_active=True
            )
            db.add(c3)
            db.commit()
            VaccineEngine.generate_child_schedule(db, c3)

            # Administer up to 9-12 months for Vihaan
            for cv in c3.vaccinations:
                if cv.vaccination_schedule.category in ["Birth", "6 Weeks", "10 Weeks", "14 Weeks", "9-12 Months"]:
                    cv.administered_date = c3.date_of_birth + timedelta(days=cv.vaccination_schedule.recommended_age_days)
                    cv.status = "administered"
                    cv.administered_by_asha_id = asha2_profile.id
                    cv.batch_number = "VAC-2025-MR301"
                    cv.session_site = "Belur Health Post"

            # Child 4: Diya Kumari (Born 14 days ago) -> Parent: Priya
            c4 = Child(
                parent_id=p1_profile.id,
                family_id=f1.id,
                village_id=v_rampur.id,
                full_name="Diya Kumari",
                date_of_birth=today - timedelta(days=14),
                gender="Female",
                birth_weight_kg=3.0,
                blood_group="B+",
                birth_place="Rampur PHC",
                mother_name="Priya Kumari",
                father_name="Ramesh Kumar",
                rch_mcp_number="RCH-RAM-2026-0099",
                house_number="12",
                parent_contact="9876533333",
                registration_date=today - timedelta(days=12),
                verification_status="verified",
                is_active=True
            )
            db.add(c4)
            db.commit()
            VaccineEngine.generate_child_schedule(db, c4)

            # Administer birth doses for Diya
            for cv in c4.vaccinations:
                if cv.vaccination_schedule.category == "Birth":
                    cv.administered_date = c4.date_of_birth
                    cv.status = "administered"
                    cv.administered_by_asha_id = asha1_profile.id
                    cv.batch_number = "VAC-2026-B505"
                    cv.session_site = "Rampur PHC Labour Room"

            # 5. Notifications
            n1 = Notification(
                user_id=p1_u.id,
                title="Vaccination Due Soon",
                message="Aarav Kumar is due for 6-Week vaccines (Pentavalent-1, OPV-1, Rotavirus-1, PCV-1). Next session on Wednesday.",
                notification_type="due_reminder"
            )
            n2 = Notification(
                user_id=p2_u.id,
                title="⚠️ Overdue Vaccination Alert",
                message="Ananya Sharma has missed 10-Week & 14-Week vaccination doses. Please visit Rampur Sub-Center immediately.",
                notification_type="overdue_alert"
            )
            db.add_all([n1, n2])

            # 6. Audit Logs
            al1 = AuditLog(
                user_id=admin_u.id,
                action="SYSTEM_INITIALIZED",
                entity_type="System",
                entity_id=1,
                details="Initial system database and UIP schedules configured.",
                ip_address="127.0.0.1"
            )
            al2 = AuditLog(
                user_id=asha1_u.id,
                action="CHILD_REGISTERED",
                entity_type="Child",
                entity_id=c1.id,
                details="Aarav Kumar registered with family ID 1 and generated UIP schedule.",
                ip_address="127.0.0.1"
            )
            db.add_all([al1, al2])
            db.commit()

            print("[SEED] Full normalized database seeded successfully!")

    finally:
        if close_at_end:
            db.close()

if __name__ == "__main__":
    seed_database()
