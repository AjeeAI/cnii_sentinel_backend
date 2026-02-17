import os
import time
import random
import traceback
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from openai import OpenAI
from geopy.geocoders import Nominatim
from typing import List, Tuple
from dotenv import load_dotenv
from schemas import CRITICAL_ZONES, ZONE_DEFAULTS, ZoneAnalysisResult, InfrastructureRisk

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
geolocator = Nominatim(user_agent="cnii_sentinel_patrol")

def resolve_coordinates(specific_location: str, parent_zone: str):
    """
    Tries to find the specific location. 
    If it fails, returns the parent zone's coordinates.
    """
    try:
        # 1. Try specific location first
        query = f"{specific_location}, Nigeria"
        location = geolocator.geocode(query, timeout=5)
        
        if location:
            return location.latitude, location.longitude
            
    except Exception:
        pass # Silently fail to fallback

    # 2. FALLBACK: Use the known zone coordinates
    print(f"   ⚠️ Could not map '{specific_location}'. Falling back to {parent_zone} center.")
    return ZONE_DEFAULTS.get(parent_zone, (9.0820, 8.6753)) # Default to Nigeria center if all else fails

def analyze_single_zone(zone_name: str, raw_text: str) -> List[InfrastructureRisk]:
    print(f"   ↳ Analyzing {zone_name} data with OpenAI...")
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are the CNII Sentinel AI. Extract infrastructure risks from construction news."},
                {"role": "user", "content": f"Zone: {zone_name}\n\nReports:\n{raw_text}"}
            ],
            response_format=ZoneAnalysisResult,
        )
        return completion.choices[0].message.parsed.risks
    except Exception as e:
        print(f"   ⚠️ OpenAI Analysis failed for {zone_name}: {e}")
        return []

def conduct_patrol_sweep(extra_zone: str = None) -> Tuple[str, List[InfrastructureRisk]]:
    driver = None
    all_risks = []
    zones_scanned = 0
    
    targets = CRITICAL_ZONES.copy()
    if extra_zone and extra_zone.lower() != "string":
        targets.append(extra_zone)

    try:
        options = uc.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

        driver = uc.Chrome(options=options, use_subprocess=True, version_main=145)

        for zone in targets:
            print(f"Scanning: {zone}...")
            try:
                search_query = f"{zone} road construction news Nigeria"
                url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
                driver.get(url)
                time.sleep(random.uniform(2.0, 4.0))

                results = driver.find_elements(By.TAG_NAME, "h3")
                zone_text = "\n".join([res.text.strip() for res in results[:3] if res.text.strip()])

                if zone_text:
                    zone_risks = analyze_single_zone(zone, zone_text)
                    
                    # --- CRITICAL UPDATE: Geocode immediately with Fallback ---
                    for risk in zone_risks:
                        lat, lng = resolve_coordinates(risk.location_identified, zone)
                        risk.latitude = lat
                        risk.longitude = lng
                        all_risks.append(risk) # Add fully hydrated risk to list
                
                zones_scanned += 1
            except Exception as e:
                print(f"Error scraping {zone}: {e}")
                continue
                
    except Exception as e:
        print(f"CRASH LOG: {traceback.format_exc()}")
        raise e
    finally:
        if driver:
            driver.quit()
            
    summary = f"Sweep complete. Scanned {zones_scanned} zones. Identified {len(all_risks)} total threats."
    return summary, all_risks