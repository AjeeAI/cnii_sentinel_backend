import traceback
from app.database import SessionLocal, PatrolReport, RiskRecord
from app.tools import perform_patrol_sweep
from app.schemas import PatrolResponse, InfrastructureRisk

def run_patrol_and_save(extra_zone: str = None) -> PatrolResponse:
    """
    Core Logic: Runs the Tavily/OpenAI sweep and saves to MySQL.
    Returns the PatrolResponse for the API (scheduler ignores return value).
    """
    print(f"⏳ Starting patrol sweep (Extra Zone: {extra_zone})...")
    
    try:
        # 1. Run the Tool (invoke returns a dict)
        result = perform_patrol_sweep.invoke({"extra_zone": extra_zone})
        
        # 2. Save to Database
        db = SessionLocal()
        try:
            new_report = PatrolReport(summary=result["summary"])
            db.add(new_report)
            db.flush() # Generate ID

            for risk in result["risks"]:
                db_risk = RiskRecord(
                    report_id=new_report.id,
                    risk_level=risk.risk_level,
                    location=risk.location_identified,
                    latitude=risk.latitude,
                    longitude=risk.longitude,
                    threat_type=risk.threat_type,
                    recommended_action=risk.recommended_action
                )
                db.add(db_risk)
            
            db.commit()
            print("✅ Patrol sweep saved to database.")
            
        except Exception as db_e:
            db.rollback()
            print(f"⚠️ Database Error: {db_e}")
            raise db_e
        finally:
            db.close()

        # 3. Return formatted response (needed for the API endpoint)
        return PatrolResponse(summary=result["summary"], risks=result["risks"])

    except Exception as e:
        print(f"❌ Patrol Task Failed: {e}")
        traceback.print_exc() # <--- Adds the full error trace to your console
        raise e