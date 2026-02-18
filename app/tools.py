import os
from typing import List, Optional
import httpx
from langchain_core.tools import tool
from tavily import TavilyClient
from openai import OpenAI
from openai import AsyncOpenAI
from geopy.geocoders import Nominatim
from app.schemas import CRITICAL_ZONES, ZONE_DEFAULTS, ZoneAnalysisResult, InfrastructureRisk

# Initialize Clients
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
# openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
geolocator = Nominatim(user_agent="cnii_sentinel_patrol")

def resolve_coordinates(specific_location: str, parent_zone: str):
    """Helper to geocode locations with fallback."""
    try:
        query = f"{specific_location}, Nigeria"
        location = geolocator.geocode(query, timeout=5)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return ZONE_DEFAULTS.get(parent_zone, (9.0820, 8.6753))

async def analyze_with_llm(zone_name: str, search_context: str) -> List[InfrastructureRisk]:
    """Helper to analyze text with OpenAI asynchronously."""
    try:
        # We use 'await' here so the server stays responsive during the AI's "thought process"
        completion = await openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are the CNII Sentinel AI. Your mission is to identify road construction "
                        "projects that pose a direct physical threat to fiber optic cables."
                    )
                },
                {"role": "user", "content": f"Zone: {zone_name}\n\nSearch Data:\n{search_context}"}
            ],
            response_format=ZoneAnalysisResult,
        )
        return completion.choices[0].message.parsed.risks
    except Exception as e:
        print(f"⚠️ OpenAI Async Error in {zone_name}: {e}")
        return []
    
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
print(f"📢 Telegram configured for chat ID: {CHAT_ID}")
print(f"📢 Telegram Bot Token: {TELEGRAM_TOKEN}")

async def send_telegram_alert(risk_level, location, summary):
    # Filter is already handled by the caller (risk_score >= 7)
    message = (
        f"🚨 *SENTINEL HIGH-PRIORITY ALERT*\n\n"
        f"📍 *Location:* {location}\n"
        f"⚠️ *Risk:* {risk_level}\n"
        f"📝 *Summary:* {summary}\n\n"
        f"🔗 [Open Dashboard](https://ai-sentinel-eye.web.app)"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        })
        
        # ADD THIS: Check if Telegram actually accepted the message
        if response.status_code != 200:
            print(f"❌ Telegram Error: {response.status_code} - {response.text}")
        else:
            print(f"✅ Telegram Alert Sent to {CHAT_ID}")


@tool
async def perform_patrol_sweep(extra_zone: Optional[str] = None) -> dict:
    """
    Scans critical infrastructure zones and triggers Telegram alerts for High Risks.
    """
    all_risks = []
    zones_scanned = 0
    
    targets = CRITICAL_ZONES.copy()
    if extra_zone and extra_zone.lower() != "string":
        targets.append(extra_zone)

    print(f"🚀 Starting Patrol Sweep on {len(targets)} zones...")

    for zone in targets:
        try:
            # 1. Search (Tavily)
            response = tavily_client.search(
                query=f"{zone} road construction news Nigeria", 
                topic="news", 
                max_results=3
            )
            results = response.get('results', [])
            search_context = "\n".join([r['content'] for r in results])
            
            if search_context:
                # 2. Analyze (OpenAI)
                zone_risks = await analyze_with_llm(zone, search_context)
                
                for risk in zone_risks:
                    # 1. Geocode the location
                    lat, lng = resolve_coordinates(risk.location_identified, zone)
                    risk.latitude = lat
                    risk.longitude = lng
                    all_risks.append(risk)

                    # 2. 🔥 THE TRIGGER: Now 'risk.risk_score' exists!
                    if risk.risk_score >= 7:
                        print(f"🚨 ALERT: High Risk detected at {risk.location_identified} ({risk.risk_score}/10)")
                        await send_telegram_alert(
                            risk_level=f"{risk.risk_score}/10",
                            location=risk.location_identified,
                            summary=risk.summary
                        )
                    
            zones_scanned += 1
        except Exception as e:
            print(f"❌ Error scanning {zone}: {e}")
            continue

    return {
        "summary": f"Sweep complete. Scanned {zones_scanned} zones. Identified {len(all_risks)} risks.",
        "risks": all_risks
    }
# Export tools list for the agent
all_tools = [perform_patrol_sweep]