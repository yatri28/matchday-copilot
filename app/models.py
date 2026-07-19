"""Request/response schemas.

Every inbound payload is validated with Pydantic before it reaches any
service code: lengths are bounded, IDs are pattern-checked, and unknown
fields are rejected.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ID_PATTERN = r"^[a-z0-9_]{1,40}$"

SupportedLanguage = Literal["en", "es", "fr", "ar", "pt", "de", "hi"]


class NavigateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue_id: str = Field(pattern=ID_PATTERN)
    start: str = Field(pattern=ID_PATTERN)
    destination: str = Field(pattern=ID_PATTERN)
    step_free_only: bool = False


class RouteStep(BaseModel):
    node_id: str
    label: str
    type: str


class NavigateResponse(BaseModel):
    found: bool
    step_free: bool
    estimated_minutes: int
    steps: list[RouteStep]
    note: Optional[str] = None


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)
    venue_id: str = Field(default="metlife", pattern=ID_PATTERN)
    language: SupportedLanguage = "en"
    accessibility_needs: bool = False


class AskResponse(BaseModel):
    answer: str
    language: SupportedLanguage
    source: Literal["genai", "offline_assistant"]
    context_used: list[str]


class ZoneDensity(BaseModel):
    zone_id: str
    label: str
    density_pct: int = Field(ge=0, le=100)
    level: Literal["low", "moderate", "high"]


class CrowdResponse(BaseModel):
    venue_id: str
    generated_at_utc: str
    zones: list[ZoneDensity]
    least_crowded_gate: Optional[str]
    advisory: str
