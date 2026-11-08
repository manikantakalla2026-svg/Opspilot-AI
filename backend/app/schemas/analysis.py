"""Strict, bounded provider-independent response contract."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(min_length=1, max_length=600)]


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    possible_cause: Text
    evidence_ids: list[Annotated[str, Field(max_length=36)]] = Field(min_length=1, max_length=20)
    recommended_checks: list[Text] = Field(min_length=1, max_length=5)
    confidence: Literal["low", "medium", "high"]


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypotheses: list[Hypothesis] = Field(min_length=1, max_length=5)
    uncertainty: Text
