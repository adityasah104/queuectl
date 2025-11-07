# queuectl/core/job.py
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class Job:
    id: str
    command: str
    state: str = "pending"
    attempts: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    run_at: str = None  # ✅ scheduled time (optional)
    priority: int = 5   # ✅ default priority (lower = higher priority)

    @classmethod
    def from_dict(cls, data):
        """Create a Job instance safely from dict input."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            command=data["command"],
            state=data.get("state", "pending"),
            attempts=data.get("attempts", 0),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
            run_at=data.get("run_at"),  # can be None or ISO string
            priority=int(data.get("priority", 5)),  # ✅ parse priority safely
        )
