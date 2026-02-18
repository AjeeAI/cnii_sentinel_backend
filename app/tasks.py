import traceback
import asyncio
from app.database import SessionLocal, PatrolReport, RiskRecord
from app.tools import perform_patrol_sweep
from app.schemas import PatrolResponse

async def run_patrol_and_save(extra_zone: str = None) -> PatrolResponse:
    """
    Tactical Update: This function is now ASYNC to support the 
    asynchronous LangChain tools and Telegram alerts.
    """
    print(f"⏳ Starting patrol sweep (Extra Zone: {extra_zone})...")
    
    try:
        # 1. Use 'ainvoke' and 'await' for async tools
        # result will be the dict returned by perform_patrol_sweep
        result = await perform_patrol_sweep.ainvoke({"extra_zone": extra_zone})
        
        # 2. Database Operation
        # Note: If your DB setup is still sync, we use it inside the async function
        db = SessionLocal()
        try:
            new_report = PatrolReport(summary=result["summary"])
            db.add(new_report)
            db.flush() 

            for risk in result["risks"]:
                db_risk = RiskRecord(
                    report_id=new_report.id,
                    risk_level=risk.risk_level,  # Corrected: Save string level here
                    risk_score=risk.risk_score,  # Corrected: Save integer score here
                    summary=risk.summary,        # Corrected: Save the summary!
                    location=risk.location_identified,
                    latitude=risk.latitude,
                    longitude=risk.longitude,
                    source_url=risk.source_url,
                    threat_type=risk.threat_type,
                    recommended_action=risk.recommended_action
                )
                db.add(db_risk)
            
            db.commit()
            print(f"✅ Patrol sweep saved. Identified {len(result['risks'])} risks.")
            
        except Exception as db_e:
            db.rollback()
            print(f"⚠️ Database Error: {db_e}")
            raise db_e
        finally:
            db.close()

        return PatrolResponse(summary=result["summary"], risks=result["risks"])

    except Exception as e:
        print(f"❌ Patrol Task Failed: {e}")
        traceback.print_exc()
        raise e