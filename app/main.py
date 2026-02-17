import json
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from langchain_core.messages import HumanMessage

# --- MODULAR IMPORTS ---
from app.database import SessionLocal, init_db, PatrolReport, RiskRecord
from app.schemas import ChatRequest, PatrolResponse, PatrolRequest, InfrastructureRisk
from app.tools import perform_patrol_sweep
from app.agent import agent 

load_dotenv()

app = FastAPI(title="CNII Sentinel API", version="2.0")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Startup
@app.on_event("startup")
def on_startup():
    init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 1. DASHBOARD ENDPOINT (Direct Tool Usage) ---
# We use the tool logic DIRECTLY here (skipping the agent) to ensure strict JSON for Flutter
@app.post("/patrol", response_model=PatrolResponse)
def start_patrol_endpoint(request: PatrolRequest):
    try:
        # invoke() calls the tool function defined in tools.py
        result = perform_patrol_sweep.invoke({"extra_zone": request.extra_zone})
        
        # Save to DB
        db = SessionLocal()
        try:
            new_report = PatrolReport(summary=result["summary"])
            db.add(new_report)
            db.flush()

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
        finally:
            db.close()

        return PatrolResponse(summary=result["summary"], risks=result["risks"])

    except Exception as e:
        print(f"CRASH: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. GET HISTORY ENDPOINT ---
@app.get("/patrol/latest", response_model=PatrolResponse)
def get_latest_report(db: Session = Depends(get_db)):
    latest_report = db.query(PatrolReport).order_by(PatrolReport.timestamp.desc()).first()
    if not latest_report:
        raise HTTPException(status_code=404, detail="No data.")

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

# --- 3. CHAT ENDPOINT (Agentic) ---
# This allows you to chat with the system: "Any risks in Lagos?"
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    message = request.message
    
    async def generate():
        async for chunk in agent.astream({"messages": [HumanMessage(content=message)]}, stream_mode="messages"):
            if isinstance(chunk, tuple) and len(chunk) >= 1:
                msg = chunk[0]
                if hasattr(msg, "content") and msg.content:
                     # Filter out tool calls, stream only answer
                    if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                        yield json.dumps({"token": msg.content}) + "\n"

    return EventSourceResponse(generate())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)