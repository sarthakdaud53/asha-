from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.models.models import LocationDistrict, LocationState, LocationSubdistrict, LocationVillage

router = APIRouter(prefix="/locations", tags=["Indian Administrative Locations"])


def _village_result(village: LocationVillage) -> dict:
    subdistrict = village.subdistrict
    district = subdistrict.district
    return {
        "id": village.id,
        "code": village.code,
        "name": village.name,
        "taluka_name": subdistrict.name,
        "district_name": district.name,
        "state_name": district.state.name,
    }


@router.get("/states")
def list_states(db: Session = Depends(get_db)) -> List[dict]:
    return [{"id": s.id, "code": s.code, "name": s.name} for s in db.query(LocationState).order_by(LocationState.name)]


@router.get("/districts")
def list_districts(state_id: int = Query(...), db: Session = Depends(get_db)) -> List[dict]:
    if not db.query(LocationState.id).filter(LocationState.id == state_id).first():
        raise HTTPException(status_code=404, detail="State not found.")
    return [{"id": d.id, "code": d.code, "name": d.name, "state_id": d.state_id}
            for d in db.query(LocationDistrict).filter(LocationDistrict.state_id == state_id).order_by(LocationDistrict.name)]


@router.get("/talukas")
def list_talukas(district_id: int = Query(...), db: Session = Depends(get_db)) -> List[dict]:
    if not db.query(LocationDistrict.id).filter(LocationDistrict.id == district_id).first():
        raise HTTPException(status_code=404, detail="District not found.")
    return [{"id": t.id, "code": t.code, "name": t.name, "district_id": t.district_id}
            for t in db.query(LocationSubdistrict).filter(LocationSubdistrict.district_id == district_id).order_by(LocationSubdistrict.name)]


@router.get("/villages")
def list_location_villages(
    taluka_id: int = Query(...),
    search: str = Query("", max_length=100),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[dict]:
    if not db.query(LocationSubdistrict.id).filter(LocationSubdistrict.id == taluka_id).first():
        raise HTTPException(status_code=404, detail="Taluka/sub-district not found.")
    query = db.query(LocationVillage).filter(LocationVillage.subdistrict_id == taluka_id)
    if search.strip():
        query = query.filter(LocationVillage.name.ilike(f"%{search.strip()}%"))
    return [_village_result(v) for v in query.order_by(LocationVillage.name).limit(limit).all()]


@router.get("/villages/{village_id}")
def get_location_village(village_id: int, db: Session = Depends(get_db)) -> dict:
    village = db.query(LocationVillage).filter(LocationVillage.id == village_id).first()
    if not village:
        raise HTTPException(status_code=404, detail="Village not found.")
    return _village_result(village)
