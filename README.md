# Digital ASHA – Rural Child Health & Vaccination Management System

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-teal.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **A production-quality rural healthcare web platform designed to eliminate survey burden, automate UIP vaccination schedules, and streamline door-to-door follow-ups for ASHA workers.**

---

## 📌 Problem Statement & Objectives

In rural India, **Accredited Social Health Activists (ASHA workers)** are the frontline backbone of maternal and child healthcare. However, they face significant operational bottlenecks:
- **Repetitive Household Visits:** Constantly conducting physical surveys to register newborns and collect demographic data.
- **Paper Register Fatigue:** Maintaining thick physical registers (Tickler registers, MCP cards) that are prone to damage and loss.
- **Manual Schedule Tracking:** Manually calculating due dates for dozens of UIP vaccines across different age milestones.
- **Follow-up Overload:** Difficulties in tracking missed booster doses and identifying high-risk or malnourished children.

### 💡 The Digital ASHA Solution
1. **Parent Self-Registration:** Parents self-register their children digitally, entering birth details and location.
2. **Automated National UIP Engine:** Based on the child's Date of Birth (DOB), the platform automatically calculates exact target dates for all 27 standard UIP vaccination doses (Birth, 6w, 10w, 14w, 9-12m, 16-24m, 5-6y, 10y, 16y) and classifies them in real time as **Upcoming**, **Due Now**, **Overdue**, or **Administered**.
3. **Proactive ASHA Field Hub:** ASHA workers monitor a live village dashboard, view automated follow-up rosters, log administered doses with batch numbers, send 1-click WhatsApp/Call reminders, and track child nutrition (MAM/SAM alerts).
4. **Official Digital MCP Card:** Instant generation and printing of standardized Mother & Child Protection cards.

---

## 👥 Three Dedicated Role Portals

| Role | Access Scope | Key Capabilities |
|---|---|---|
| **Parent** | Own Children | Self-register children, interactive UIP immunization timeline, digital MCP card print, growth tracking, direct contact with assigned village ASHA worker. |
| **ASHA Worker** | Assigned Village | Village KPI metrics, automated Due & Overdue follow-up planner, 1-click WhatsApp outreach, log administered vaccines (batch, site, AEFI), child growth monitoring (MAM/SAM alerts), verify parent submissions. |
| **Admin** | Block / District | PHC and Sub-Center coverage analytics, village territory creation, ASHA worker allocation, Universal Immunization Programme master schedule catalog. |

---

## 🏗️ Architecture & Project Structure

```
digital_asha/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                 # JWT Auth & Role-Based Access Control (RBAC)
│   │   │   └── routers/
│   │   │       ├── auth.py             # User register, login, profile
│   │   │       ├── children.py         # Child CRUD, status calculation, verification
│   │   │       ├── vaccines.py         # National UIP Master schedule catalog
│   │   │       ├── immunizations.py    # Log administered dose, digital MCP card
│   │   │       ├── growth.py           # Child weight/height/MUAC & SAM/MAM alerts
│   │   │       ├── asha.py             # Village KPIs, follow-up home visit planner
│   │   │       └── admin.py            # Village assignments & district stats
│   │   ├── core/
│   │   │   ├── config.py               # Pydantic Settings & environment loader
│   │   │   └── security.py             # Bcrypt password hashing & JWT tokens
│   │   ├── db/
│   │   │   ├── database.py             # SQLAlchemy engine & session factory
│   │   │   └── seed.py                 # Full National UIP schedule & demo rural dataset
│   │   ├── models/
│   │   │   └── models.py               # Relational schema (User, Village, Child, Vaccine, etc.)
│   │   ├── schemas/
│   │   │   └── schemas.py              # Pydantic validation & response schemas
│   │   ├── services/
│   │   │   ├── vaccine_engine.py       # Dynamic UIP due date calculation engine
│   │   │   ├── growth_service.py       # WHO/IAP child nutrition evaluation (SAM/MAM)
│   │   │   └── notification_service.py # In-app alerts & reminders
│   │   └── main.py                     # FastAPI application & static asset mounts
│   ├── tests/                          # Automated Pytest suite (10 test cases)
│   ├── requirements.txt
│   └── run.py                          # Application startup script
├── frontend/
│   ├── css/
│   │   └── custom.css                  # Healthcare palette & printable MCP card styles
│   ├── js/
│   │   ├── api.js                      # Centralized API service with JWT headers
│   │   ├── auth.js                     # Session management & role protection
│   │   ├── utils.js                    # Toasts, date formatters, badges, WhatsApp links
│   │   ├── parent.js                   # Parent dashboard controller
│   │   ├── asha.js                     # ASHA field operations controller
│   │   └── admin.js                    # Admin dashboard controller
│   ├── index.html                      # Landing page, role cards, 1-click demo logins
│   ├── parent.html                     # Parent Portal
│   ├── asha.html                       # ASHA Worker Portal
│   └── admin.html                      # Health Administrator Portal
├── .env.example
├── .env
├── pytest.ini
└── README.md
```

---

## ⚡ Quick Start Guide

### 1. Prerequisites
- Python 3.10+ installed

### 2. Installation & Setup
```bash
# Clone or navigate to the project directory
cd "community engagement"

# Create and activate virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Run Automated Tests
```bash
pytest -v
```

### 4. Start the Application
```bash
python backend/run.py
```
Open your browser and navigate to: **[http://localhost:8000](http://localhost:8000)**

---

## 🔑 Demo Login Credentials

You can use the 1-click demo login buttons directly on the landing page (`http://localhost:8000`) or sign in with:

| Role | Username | Password | Full Name / Description |
|---|---|---|---|
| **Parent** | `parent_priya` | `parent123` | Priya Kumari (Mother of Aarav & Diya - Rampur Village) |
| **Parent** | `parent_anita` | `parent123` | Anita Sharma (Mother of Ananya - Overdue alert demo) |
| **ASHA Worker** | `asha_sunita` | `asha123` | Sunita Devi (ASHA Worker - Rampur Village) |
| **ASHA Worker** | `asha_rekha` | `asha123` | Rekha Bai (ASHA Worker - Belur Village) |
| **Admin** | `admin` | `admin123` | Dr. Rajesh Sharma (Block Medical Officer) |

---

## 💉 Pre-Configured National UIP Immunization Schedule

The system comes pre-seeded with the complete **Universal Immunization Programme (UIP India)** schedule:

1. **At Birth:** BCG, OPV-0, Hepatitis B-0
2. **6 Weeks:** OPV-1, Pentavalent-1, Rotavirus-1, Fractional IPV-1, PCV-1
3. **10 Weeks:** OPV-2, Pentavalent-2, Rotavirus-2
4. **14 Weeks:** OPV-3, Pentavalent-3, Rotavirus-3, Fractional IPV-2, PCV-2
5. **9–12 Months:** Measles & Rubella-1 (MR-1), Japanese Encephalitis-1 (JE-1), PCV Booster, Vitamin A (1st Dose)
6. **16–24 Months:** MR-2, JE-2, DPT Booster-1, OPV Booster, Vitamin A (2nd Dose)
7. **5–6 Years:** DPT Booster-2
8. **10 Years:** Td (Tetanus & adult Diphtheria)
9. **16 Years:** Td (Late adolescent booster)

---

## 📊 Evaluation & Verification Checklist

- [x] Full-stack architecture (FastAPI backend + responsive frontend).
- [x] Relational database with foreign keys and automatic seeder.
- [x] JWT authentication with secure password hashing and role enforcement (`parent`, `asha`, `admin`).
- [x] Universal Immunization Programme (UIP) dynamic date calculation engine.
- [x] Parent panel with child self-registration, timeline, and MCP card generator.
- [x] ASHA panel with village KPIs, due/overdue planner, WhatsApp reminder builder, dose recording, and SAM/MAM alerts.
- [x] Admin panel with village territory management, ASHA staff allocation, and coverage statistics.
- [x] 100% test pass rate with automated Pytest suite.
- [x] Environment configuration template (`.env.example` and `.env`).
