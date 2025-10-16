from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from typing import Optional
import uuid

# ---------- Users ----------
@dataclass
class User:
    user_id: str
    name: str
    email: str
    role: str                 # 'USER' | 'ADMIN'
    created_at: str
    # Demo-only: store password hash separately in memory (not returned)
    password_hash: str

    @staticmethod
    def new(name: str, email: str, role: str, password_hash: str) -> "User":
        return User(
            user_id=str(uuid.uuid4()),
            name=name,
            email=email.lower(),
            role=role.upper(),
            created_at=datetime.now(UTC).isoformat(),
            password_hash=password_hash,
        )

    def to_public(self) -> dict:
        # What you return to clients
        d = asdict(self)
        d.pop("password_hash", None)
        return d

# ---------- Events ----------
@dataclass
class Event:
    event_id: str
    event_image: Optional[str]  # base64
    title: str
    description: Optional[str]
    venue: str
    venue_image: Optional[str]  # base64
    date: str                   # ISO timestamp string
    total_seats: int
    price: float
    created_by: Optional[str]   # user_id of admin
    created_at: str

    @staticmethod
    def new(title: str, description: Optional[str], venue: str,
            date: str, total_seats: int, price: float,
            created_by: Optional[str],
            event_image: Optional[str] = None,
            venue_image: Optional[str] = None,
            event_id: Optional[str] = None) -> "Event":
        return Event(
            event_id=event_id or str(uuid.uuid4()),
            event_image=event_image,
            title=title,
            description=description,
            venue=venue,
            venue_image=venue_image,
            date=str(date),
            total_seats=int(total_seats),
            price=float(price),
            created_by=created_by,
            created_at=datetime.now(UTC).isoformat(),
        )

    def to_dict(self) -> dict:
        return asdict(self)
