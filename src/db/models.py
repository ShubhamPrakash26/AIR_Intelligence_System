from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON


class IncidentRecord(SQLModel, table=True):
    incident_id: str = Field(primary_key=True)
    parsed_incident: dict = Field(sa_column=Column(JSON), default_factory=dict)
    source_file: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnalysisRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(index=True)
    analysis: dict = Field(sa_column=Column(JSON), default_factory=dict)
    model_version: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
