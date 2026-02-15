import os
import time
import traceback
import undetected_chromedriver as uc
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List
from google import genai
from google.genai import types
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

load_dotenv()

app = FastAPI()

# 1. Global Storage (In a real app, use a Database like SQLite)
latest_findings = {"last_updated": None, "data": None}

# --- Schema Setup (Unchanged) ---
class InfrastructureRisk(BaseModel):
    risk_level: str
    location_identified: str
    threat_type: str
    recommended_action: str

class PatrolResponse(BaseModel):
    summary: str
    risks: List[InfrastructureRisk]

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. The Core Scraping Logic (Extracted for reusability)
def run_automated_patrol():
    global latest_findings
    print(f"[{datetime.now()}] Starting periodic infrastructure patrol...")
    driver = None
    try:
        options = uc.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        
        # Adjust version_main to your Chrome version
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=145) 
        
        # Broad search to catch multiple risks
        search_query = "Lagos road construction fiber risk"
        url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        driver.get(url)
        time.sleep(3)

        results = driver.find_elements(By.TAG_NAME, "h3")
        raw_text_data = "".join([f"- {res.text}\n" for res in results[:6] if res.text])

        if raw_text_data:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=f"Analyze these reports for telco fiber risks: {raw_text_data}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=PatrolResponse,
                )
            )
            # Update the global storage
            latest_findings["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            latest_findings["data"] = response.parsed
            print("Patrol Complete. Results updated.")
    except Exception:
        print(f"Background Patrol Failed: {traceback.format_exc()}")
    finally:
        if driver: driver.quit()

# 3. Schedule the task (Every 6 hours)
scheduler = BackgroundScheduler()
scheduler.add_job(run_automated_patrol, 'interval', hours=6)
scheduler.start()

# 4. API Endpoints
@app.get("/latest-risks")
def get_latest():
    """Endpoint for your Flutter app to fetch the most recent data"""
    if not latest_findings["data"]:
        return {"status": "Processing first crawl..."}
    return latest_findings

@app.on_event("startup")
def startup_event():
    """Optional: Run once on startup so you don't wait 6 hours for the first data"""
    # run_automated_patrol() 
    pass