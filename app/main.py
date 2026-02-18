import os
import json
import traceback
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from langchain_core.messages import HumanMessage
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
import httpx

# --- MODULAR IMPORTS ---
from app.database import SessionLocal, init_db, PatrolReport
from app.schemas import PatrolResponse, PatrolRequest, InfrastructureRisk, ChatRequest
from app.agent import agent 
# NEW: Import the task logic
from app.tasks import run_patrol_and_save

load_dotenv()

# --- SCHEDULER SETUP ---
# scheduler = BackgroundScheduler()
scheduler = AsyncIOScheduler()
def configure_scheduler():
    env_mode = os.getenv("ENVIRONMENT", "TESTING").upper()
    
    # Define Nigeria Time
    lagos_time = timezone('Africa/Lagos')
    
    if env_mode == "PRODUCTION":
        # Pass the timezone to the cron trigger
        scheduler.add_job(run_patrol_and_save, 'cron', hour=7, minute=0, timezone=lagos_time)
        print("🕒 Scheduler: PRODUCTION Mode (Daily at 7:00 AM Lagos Time)")
    else:
        scheduler.add_job(run_patrol_and_save, 'interval', minutes=10)
        print("🕒 Scheduler: TESTING Mode (Every 10 minutes)")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    print("🚀 Sentinel System Starting...")
    init_db()
    configure_scheduler()
    scheduler.start()
    yield
    # --- SHUTDOWN ---
    print("🛑 Sentinel System Shutting Down...")
    scheduler.shutdown()

app = FastAPI(title="CNII Sentinel API", version="2.1", lifespan=lifespan)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
async def health_check():
    return {"status": "online", "message": "Sentinel Brain is active"}
# --- 1. DASHBOARD ENDPOINT (Refactored) ---
@app.post("/patrol", response_model=PatrolResponse)
async def start_patrol_endpoint(request: PatrolRequest):
    try:
        # REFACTOR: Just call the shared task function!
        # This keeps your code DRY (Don't Repeat Yourself)
        return await run_patrol_and_save(request.extra_zone)
    except Exception as e:
        print(f"CRASH: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. GET HISTORY ENDPOINT ---
@app.get("/patrol/latest", response_model=PatrolResponse)
def get_latest_report(db: Session = Depends(get_db)):
    latest_report = db.query(PatrolReport).order_by(PatrolReport.timestamp.desc()).first()
    if not latest_report:
        raise HTTPException(status_code=404, detail="No data.")

    # 1. Define Priority Map
    priority_map = {
        "High": 3, 
        "Medium": 2, 
        "Low": 1
    }

    # 2. Sort risks (High -> Low)
    # We use .get(..., 0) to handle unexpected values safely
    sorted_db_risks = sorted(
        latest_report.risks, 
        key=lambda r: priority_map.get(r.risk_level, 0), 
        reverse=True
    )

    # 3. Format for Response
    formatted_risks = [
    InfrastructureRisk(
        risk_level=r.risk_level,
        risk_score=r.risk_score if r.risk_score is not None else 0, # Fallback to 0
        summary=r.summary if r.summary is not None else "No summary available", # Fallback string
        location_identified=r.location,
        threat_type=r.threat_type,
        recommended_action=r.recommended_action,
        latitude=r.latitude,
        longitude=r.longitude,
        source_url=r.source_url
    ) for r in sorted_db_risks
]
    
    return PatrolResponse(summary=latest_report.summary, risks=formatted_risks)

# --- 3. CHAT ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    message = request.message 
    
    async def generate():
        try:
            async for chunk in agent.astream({"messages": [HumanMessage(content=message)]}, stream_mode="messages"):
                if isinstance(chunk, tuple) and len(chunk) >= 1:
                    msg = chunk[0]
                    if hasattr(msg, "content") and msg.content:
                        if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                            yield json.dumps({"token": msg.content}) + "\n"
        except Exception as e:
            print(f"Streaming Error: {e}")
            yield json.dumps({"error": str(e)}) + "\n"

    return EventSourceResponse(generate())

@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Sentinel Connections Closed.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)