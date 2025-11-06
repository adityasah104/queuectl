import uuid
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class Job:
    command: str                          # non-default first
    id: str = str(uuid.uuid4())           # default unique ID
    state: str = "pending"
    attempts: int = 0
    max_retries: int = 3
    created_at: str = datetime.utcnow().isoformat()
    updated_at: str = datetime.utcnow().isoformat()

    @staticmethod
    def from_dict(data: dict):
        return Job(
            command=data["command"],
            id=data.get("id", str(uuid.uuid4())),
            state=data.get("state", "pending"),
            attempts=data.get("attempts", 0),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )

    def to_dict(self):
        return asdict(self)
