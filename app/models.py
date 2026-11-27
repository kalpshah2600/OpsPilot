from pydantic import BaseModel, Field
from typing import Literal

class Evidence(BaseModel):
    source: str
    summary: str
    value: str | float | int | None = None
    severity: Literal["info", "warning", "critical"] = "info"

class InvestigationRequest(BaseModel):
    question: str = Field(min_length=3)

class InvestigationResult(BaseModel):
    incident_id: str
    question: str
    root_cause: str
    confidence: float
    evidence: list[Evidence]
    recommended_action: str
    requires_approval: bool = True
    status: str = "proposed"

class ApprovalRequest(BaseModel):
    incident_id: str
    action: str
    approved_by: str = "demo-user"
