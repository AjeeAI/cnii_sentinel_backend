from pydantic import BaseModel, Field
from typing import List, Optional

# --- Constants ---
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

ZONE_DEFAULTS = {
    "Lagos-Ibadan Expressway": (6.9530, 3.6157),
    "Lagos-Abeokuta Expressway": (6.7020, 3.2570),
    "Lekki-Epe Expressway": (6.4716, 3.7297),
    "Akwa Ibom Kwa Ibo fiber route": (4.6544, 7.9254),
    "Abuja-Kaduna Expressway": (9.6844, 7.8288),
    "Benin-Ore Road": (6.5980, 5.2373),
    "Port Harcourt-Enugu Expressway": (5.5074, 7.2343),
    "Kano-Zaria Road": (11.5363, 8.0827)
}

# --- Models ---
class InfrastructureRisk(BaseModel):
    risk_level: str = Field(description="Low, Medium, or High")
    location_identified: str = Field(description="Street or area name found in text")
    threat_type: str = Field(description="e.g., Excavation, Road Grading, Drainage Works")
    recommended_action: str = Field(description="Specific directive for patrol teams")
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ZoneAnalysisResult(BaseModel):
    risks: List[InfrastructureRisk]

class PatrolResponse(BaseModel):
    summary: str
    risks: List[InfrastructureRisk]

class PatrolRequest(BaseModel):
    extra_zone: Optional[str] = None
    
# --- NEW: Chat Request Model ---
class ChatRequest(BaseModel):
    message: str