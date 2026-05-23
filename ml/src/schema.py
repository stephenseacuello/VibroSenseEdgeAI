"""Versioned payload schemas shared by gateway, app, and tests.

See PROJECT_PLAN.md §14, ADR-0001 (state), and the Node-RED alarm publisher in
`gateway/nodered/flows.json` (alarm).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CLASS_LABELS: tuple[str, ...] = ("HEALTHY", "IMBALANCE", "LOOSENESS", "BEARING_FAULT")

ClassLabel = Literal["HEALTHY", "IMBALANCE", "LOOSENESS", "BEARING_FAULT"]


class StateV1(BaseModel):
    """The `state` characteristic / MQTT payload, schema v1."""

    schema_ver: Literal[1] = 1
    ts_ms: Optional[int] = None
    ts_utc: Optional[str] = None
    seq: int = Field(ge=0)
    state: ClassLabel
    confidence: float = Field(ge=0.0, le=1.0)
    asset_id: Optional[str] = None


class AlarmV1(BaseModel):
    """The `pdm/{asset_id}/alarm` MQTT payload emitted by Node-RED, schema v1.

    `from` is a Python keyword so we expose it on the model as `from_state` but
    accept either name when parsing JSON. The DB column is `from_state` to keep
    the SQL ergonomic.
    """

    model_config = ConfigDict(populate_by_name=True)

    schema_ver: Literal[1] = 1
    asset_id: str
    ts_utc: str
    from_state: Optional[ClassLabel] = Field(default=None, alias="from")
    to_state: ClassLabel = Field(alias="to")
    confidence: float = Field(ge=0.0, le=1.0)
