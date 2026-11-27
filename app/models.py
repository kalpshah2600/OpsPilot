from pydantic import BaseModel, Field
from typing import Literal

class Evidence(BaseModel):
    source: str
    summary: str
    value: str | float | int | None = None
    severity: Literal["info", "warning", "critical"] = "info"
    details: dict | None = None

class Hypothesis(BaseModel):
    key: str
    label: str
    confidence: float = Field(ge=0, le=1)
    rationale: list[str] = []

class InvestigationRequest(BaseModel):
    question: str = Field(min_length=3)

class InvestigationResult(BaseModel):
    incident_id: str
    question: str
    root_cause: str
    root_cause_key: str
    confidence: float
    evidence: list[Evidence]
    hypotheses: list[Hypothesis] = []
    recommended_action: str
    requires_approval: bool = True
    status: str = "proposed"
    reasoner: str = "rules"

class ApprovalRequest(BaseModel):
    incident_id: str
    action: str
    approved_by: str = "demo-user"
