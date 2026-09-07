"""Import the real Indian administrative hierarchy from an LGD snapshot."""

import csv
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.models.models import (
    LocationDistrict,
    LocationState,
    LocationSubdistrict,
    LocationVillage,
)

SOURCE = "Local Government Directory, Ministry of Panchayati Raj"
SOURCE_URL = "https://lgdirectory.gov.in/"
SNAPSHOT = "village-directory.csv (LGD archive; downloaded 2026-09-07)"


def import_lgd_snapshot(db: Session, csv_path: Path) -> dict[str, int]:
    if not csv_path.exists() or db.query(LocationState).count():
        return {"states": db.query(LocationState).count(), "districts": db.query(LocationDistrict).count(),
                "subdistricts": db.query(LocationSubdistrict).count(), "villages": db.query(LocationVillage).count()}

    states = {}
    districts = {}
    subdistricts = {}
    villages = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            state_code = row["State code"].strip()
            district_code = row["District code"].strip()
            subdistrict_code = row["Subdistrict code"].strip()
            village_code = row["Village code"].strip()
            states.setdefault(state_code, row["State Name(In English)"].strip())
            districts.setdefault(district_code, (row["District Name(In English)"].strip(), state_code))
            subdistricts.setdefault(subdistrict_code, (row["Subdistrict Name(In English)"].strip(), district_code))
            villages.setdefault(village_code, (row["Village Name(In English)"].strip(), subdistrict_code))

    state_rows = {code: LocationState(code=code, name=name, source=SOURCE, source_version=SNAPSHOT)
                  for code, name in states.items()}
    db.add_all(state_rows.values())
    db.flush()
    district_rows = {}
    for code, (name, state_code) in districts.items():
        district_rows[code] = LocationDistrict(code=code, name=name, state=state_rows[state_code])
    db.add_all(district_rows.values())
    db.flush()
    subdistrict_rows = {}
    for code, (name, district_code) in subdistricts.items():
        subdistrict_rows[code] = LocationSubdistrict(code=code, name=name, district=district_rows[district_code])
    db.add_all(subdistrict_rows.values())
    db.flush()
    db.add_all(LocationVillage(code=code, name=name, subdistrict=subdistrict_rows[subdistrict_code])
                for code, (name, subdistrict_code) in villages.items())
    db.commit()
    return {"states": len(states), "districts": len(districts), "subdistricts": len(subdistricts), "villages": len(villages)}
