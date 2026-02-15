import os
import time
import random
import traceback
import undetected_chromedriver as uc
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv
from selenium.webdriver.common.by import By

load_dotenv()

app = FastAPI()

# --- 1. The Asset Registry (Moved to Global Scope) ---
CRITICAL_ZONES = [
    "Lagos-Ibadan Expressway",
    "Lagos-Abeokuta Expressway",
    "Lekki-Epe Expressway",
    "Akwa Ibom Kwa Ibo fiber route", 
    "Abuja-Kaduna Expressway",
    "Benin-Ore Road",
    "Port Harcourt-Enugu Expressway",
    "Kano-Zaria Road"
]

# --- 2. Schema Setup ---
class InfrastructureRisk(BaseModel):
    risk_level: str = Field(description="Low, Medium, or High")
    location_identified: str = Field(description="Street or area name found in text")
    threat_type: str = Field(description="e.g., Excavation, Road Grading, Drainage Works")
    recommended_action: str = Field(description="Specific directive for Airtel/9mobile patrol teams")

class PatrolResponse(BaseModel):
    summary: str
    risks: List[InfrastructureRisk]

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# We don't need a request body anymore because the "Sweep" is pre-defined
# But we can keep an optional one if you want to add a specific zone on the fly
class PatrolRequest(BaseModel):
    extra_zone: Optional[str] = None

@app.post("/patrol", response_model=PatrolResponse)
def start_patrol(request: PatrolRequest):
    driver = None
    try:
        options = uc.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

        # Force version_main if necessary (check your chrome://version)
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=145)
        
        # Build the Target List (Defaults + any extra)
        targets = CRITICAL_ZONES.copy()
        if request.extra_zone:
            targets.append(request.extra_zone)

        aggregated_raw_data = ""
        
        print(f"Starting sweep of {len(targets)} critical zones...")

        # --- THE LOOP: Iterating through the Asset Registry ---
        for zone in targets:
            print(f"Scanning: {zone}...")
            try:
                # Add 'road construction' to ensure relevance
                search_query = f"{zone} road construction news Nigeria"
                url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
                
                driver.get(url)
                
                # Random sleep to behave like a human moving between tabs
                time.sleep(random.uniform(2.0, 4.0))

                results = driver.find_elements(By.TAG_NAME, "h3")
                
                zone_findings = ""
                count = 0
                for res in results:
                    text = res.text.strip()
                    if text and len(text) > 10 and "People also ask" not in text:
                        zone_findings += f"- {text}\n"
                        count += 1
                    if count >= 3: break # Limit to top 3 per zone to save time
                
                if zone_findings:
                    aggregated_raw_data += f"\n--- REPORT FOR {zone.upper()} ---\n{zone_findings}"
            
            except Exception as e:
                print(f"Error scraping {zone}: {e}")
                continue # Keep going to the next zone even if one fails

        # --- Debugging ---
        if not aggregated_raw_data:
            driver.save_screenshot("debug_sweep_fail.png")
            raise Exception("Sweep returned no data. Google might be blocking the bulk requests.")

        # --- Gemini 3 Analysis (One Big Intelligence Briefing) ---
        print("Sending aggregated intelligence to Gemini...")
        prompt = f"""
        You are the CNII Sentinel AI. 
        I have just performed a web sweep of the entire Airtel/9mobile fiber backbone.
        
        Here is the raw intelligence from multiple regions:
        {aggregated_raw_data}
        
        Analyze this immediately. Group similar threats. 
        If a region has no relevant construction news, ignore it.
        Focus on Heavy Machinery, Excavation, and Federal Works.
        """

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PatrolResponse,
            )
        )

        return response.parsed

    except Exception as e:
        print(f"CRASH LOG: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    import uvicorn
    # Increased timeout_keep_alive because this sweep might take 30-40 seconds
    uvicorn.run("patrol:app", host="127.0.0.1", port=8000, reload=True, timeout_keep_alive=60)