import os
from typing import List
from langchain_core.tools import tool
from tavily import TavilyClient
from openai import OpenAI
from geopy.geocoders import Nominatim
from app.schemas import CRITICAL_ZONES, ZONE_DEFAULTS, ZoneAnalysisResult, InfrastructureRisk

# Initialize Clients
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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

def analyze_with_llm(zone_name: str, search_context: str) -> List[InfrastructureRisk]:
    """Helper to analyze text with OpenAI."""
    try:
        completion = openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are the CNII Sentinel AI. Analyze search results for fiber optic infrastructure risks."},
                {"role": "user", "content": f"Zone: {zone_name}\n\nResults:\n{search_context}"}
            ],
            response_format=ZoneAnalysisResult,
        )
        return completion.choices[0].message.parsed.risks
    except Exception as e:
        print(f"⚠️ Analysis Error: {e}")
        return []

@tool
def perform_patrol_sweep(extra_zone: str = None) -> dict:
    """
    Scans critical infrastructure zones for construction risks using Tavily Search.
    Returns a dictionary with 'summary' and 'risks'.
    """
    all_risks = []
    zones_scanned = 0
    
    targets = CRITICAL_ZONES.copy()
    if extra_zone and extra_zone.lower() != "string":
        targets.append(extra_zone)

    print(f"🚀 Starting Patrol Sweep on {len(targets)} zones...")

    for zone in targets:
        try:
            # 1. Search
            response = tavily_client.search(
                query=f"{zone} road construction news Nigeria", 
                topic="news", 
                max_results=3
            )
            # Handle Tavily response format safely
            results = response.get('results', [])
            search_context = "\n".join([r['content'] for r in results])
            
            if search_context:
                # 2. Analyze
                zone_risks = analyze_with_llm(zone, search_context)
                
                # 3. Geocode
                for risk in zone_risks:
                    lat, lng = resolve_coordinates(risk.location_identified, zone)
                    risk.latitude = lat
                    risk.longitude = lng
                    all_risks.append(risk)
                    
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