from datetime import datetime
from types import SimpleNamespace

from app.core.security import hash_password


def make_user(**overrides):
    values = {
        "id": 1,
        "email": "user@example.com",
        "password": hash_password("password123"),
        "nickname": "tester",
        "profile_image_seed": "tester",
        "job_type": "employee",
        "monthly_salary": 3_000_000,
        "is_email_verified": True,
        "provider": "local",
        "social_id": None,
        "onboarding_step": 0,
        "created_at": datetime(2026, 7, 27),
        "updated_at": datetime(2026, 7, 27),
    }
    values.update(overrides)
    return SimpleNamespace(**values)
