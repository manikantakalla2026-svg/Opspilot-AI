import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Name must contain at least two non-space characters")
        return value.strip()


class ServiceUpdate(ServiceCreate):
    active: bool = True


class ServiceOut(ServiceUpdate):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LogInput(BaseModel):
    timestamp: AwareDatetime | None = None
    severity: Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
    message: str = Field(min_length=1, max_length=4000)
    error_type: str = Field(default="", max_length=100)
    endpoint: str = Field(default="", max_length=200)
    correlation_id: str | None = Field(default=None, max_length=100)
    metadata: dict = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def bounded_metadata(cls, value):
        if len(json.dumps(value)) > 4000:
            raise ValueError("Metadata exceeds 4000 characters")
        return value


class IncidentUpdate(BaseModel):
    status: Literal["Open", "Investigating", "Resolved"]


class SimulationInput(BaseModel):
    service_id: UUID
    scenario: Literal["payment_timeout", "database_timeout", "exception", "normal"] = "payment_timeout"
