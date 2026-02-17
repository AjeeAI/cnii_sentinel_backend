from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, PatrolReport, RiskRecord
from schemas import PatrolResponse, PatrolRequest, InfrastructureRisk
from services import conduct_patrol_sweep 

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/patrol/latest", response_model=PatrolResponse)
def get_latest_report(db: Session = Depends(get_db)):
    latest_report = db.query(PatrolReport).order_by(PatrolReport.timestamp.desc()).first()
    if not latest_report:
        raise HTTPException(status_code=404, detail="No patrol reports found.")

    formatted_risks = [
        InfrastructureRisk(
            risk_level=r.risk_level,
            location_identified=r.location,
            threat_type=r.threat_type,
            recommended_action=r.recommended_action,
            latitude=r.latitude,
            longitude=r.longitude
        ) for r in latest_report.risks
    ]

    return PatrolResponse(summary=latest_report.summary, risks=formatted_risks)

@router.post("/patrol", response_model=PatrolResponse)
def start_patrol(request: PatrolRequest):
    # 1. Run the heavy lifting (Service Layer) - NOW INCLUDES GEOCODING
    try:
        summary_text, all_risks = conduct_patrol_sweep(request.extra_zone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 2. Save to Database (Data Layer)
    print("💾 Saving report to database...")
    db = SessionLocal()
    try:
        new_report = PatrolReport(summary=summary_text)
        db.add(new_report)
        db.flush()

        for risk in all_risks:
            # Note: risk.latitude/longitude are already populated by services.py
            db_risk = RiskRecord(
                report_id=new_report.id,
                risk_level=risk.risk_level,
                location=risk.location_identified,
                latitude=risk.latitude,   # <--- Guaranteed not null
                longitude=risk.longitude, # <--- Guaranteed not null
                threat_type=risk.threat_type,
                recommended_action=risk.recommended_action
            )
            db.add(db_risk)
        
        db.commit()
        print("✅ Patrol report saved successfully.")
    except Exception as db_e:
        db.rollback()
        print(f"⚠️ Database Error: {db_e}")
    finally:
        db.close()

    return PatrolResponse(summary=summary_text, risks=all_risks)