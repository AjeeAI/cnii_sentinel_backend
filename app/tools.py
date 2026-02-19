import os
from typing import List, Optional
import httpx
from langchain_core.tools import tool
from tavily import TavilyClient

from tavily import AsyncTavilyClient
from openai import OpenAI
from openai import AsyncOpenAI
from geopy.geocoders import Nominatim
from app.schemas import CRITICAL_ZONES, ZONE_DEFAULTS, ZoneAnalysisResult, InfrastructureRisk

# Initialize Clients
# tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
tavily_client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
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
                        "### ROLE\n"
                        "You are a Senior Nigerian Infrastructure Security Analyst specializing in "
                        "Critical National Information Infrastructure (CNII).\n\n"
                        
                        "### MISSION\n"
                        "Identify road construction, dredging, or excavation projects in NIGERIA "
                        "that pose a physical threat to fiber optic backbone cables.\n\n"
                        
                        "STRICT RULE: For every risk identified, you MUST provide the 'URL' of the "
                        "source where you found that specific information. Do not guess; use the "
                        "provided URL labels in the context."

                        "### STRICT GEOGRAPHIC RULES\n"
                        "1. ONLY process data related to Nigeria (Lagos, Abuja, PH, etc.).\n"
                        "2. IMMEDIATELY DISCARD any results from the UK, USA, or other countries.\n"
                        "3. If you see 'Melton Mowbray' or 'Leicestershire', ignore it. It is out of scope.\n"
                        "4. If no Nigerian risks are found in the text, return an empty list: [].\n\n"
                        
                        "### ANALYSIS CRITERIA\n"
                        "Look for: 'road expansion', 'drainage works', 'bridge construction', or 'digging' "
                        "in proximity to known telecommunications routes."
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


async def fetch_clean_content(url: str) -> str:
    """The 'Sniper': Fetches clean, LLM-ready text using Jina Reader."""
    try:
        async with httpx.AsyncClient() as client:
            # Prepending r.jina.ai/ extracts the main content and strips sidebars
            response = await client.get(f"https://r.jina.ai/{url}", timeout=10)
            return response.text if response.status_code == 200 else ""
    except Exception:
        return ""

@tool
async def perform_patrol_sweep(extra_zone: Optional[str] = None) -> dict:
    """
    Scans critical infrastructure zones using Tavily search and cleans article content 
    with Jina Reader to identify fiber optic risks in Nigeria.
    """
    all_risks = []
    targets = CRITICAL_ZONES.copy()
    if extra_zone and extra_zone.lower() != "string":
        targets.append(extra_zone)

    for zone in targets:
        try:
            # STEP 1: The 'Scout' (Tavily find URLs)
            search = await tavily_client.search(
                query=f'"{zone}" Nigeria road construction fiber optic damage', 
                topic="news", max_results=3, search_depth="advanced"
            )
            
            results = search.get('results', [])
            search_context = ""
            
            for i, r in enumerate(results):
                # STEP 2: The 'Sniper' (Fetch full clean text)
                clean_text = await fetch_clean_content(r['url'])
                content_to_use = clean_text if len(clean_text) > 200 else r['content']
                
                # STEP 3: Labeled Context for the AI
                search_context += (
                    f"--- SOURCE [{i}] ---\n"
                    f"TITLE: {r.get('title')}\n"
                    f"DATE: {r.get('published_date')}\n"
                    f"URL: {r['url']}\n"
                    f"CONTENT: {content_to_use}\n\n"
                )

            if search_context:
                zone_risks = await analyze_with_llm(zone, search_context)
                for risk in zone_risks:
                    lat, lng = resolve_coordinates(risk.location_identified, zone)
                    risk.latitude, risk.longitude = lat, lng
                    all_risks.append(risk)
                    
                    if risk.risk_score >= 7:
                        await send_telegram_alert(
                            risk_level=f"{risk.risk_score}/10",
                            location=risk.location_identified,
                            summary=risk.summary
                        )
        except Exception as e:
            print(f"❌ Error scanning {zone}: {e}")
    
    return {"summary": f"Sweep complete. Identified {len(all_risks)} risks.", "risks": all_risks}
# Export tools list for the agent
all_tools = [perform_patrol_sweep]