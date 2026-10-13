from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monitoring_only: bool = True
    cpu_enabled: bool = False
    memory_enabled: bool = False
    anomaly_response: bool = False
    alpha: float = Field(.3, gt=0, le=1)
    threshold: float = Field(.55, ge=.2, le=.95)
    interval: float = Field(1, ge=.5, le=10)
    training_windows: int = Field(12, ge=5, le=120)
    cooldown: float = Field(5, ge=2, le=120)


class Sample(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    identity: str
    pid: int = Field(ge=1)
    name: str
    group: str
    timestamp: float
    source: Literal["simulated", "linux-ebpf", "linux-proc"]
    cpu: float = Field(ge=0)
    burst_ms: float = Field(ge=0)
    switches: int = Field(ge=0)
    faults: float = Field(ge=0)
    memory_mb: float = Field(ge=0)
    pressure: float = Field(ge=0, le=100)
    io_bytes: float = Field(0, ge=0)
    syscalls: list[int] = Field(default_factory=list, max_length=8192)
    syscall_count: int = Field(0, ge=0)
    drops: int = Field(0, ge=0)
    event_count: int = Field(0, ge=0)
    sequence_truncated: int = Field(0, ge=0)
    event_latency_ms: float | None = Field(None, ge=0)
    cgroup_stats: dict = Field(default_factory=dict)
    label: bool | None = None
