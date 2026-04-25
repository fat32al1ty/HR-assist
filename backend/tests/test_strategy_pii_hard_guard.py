"""Phase 5.2.4 — PII hard guard: cover letter draft must never leak PII.

Template mode only (deterministic). 30 synthetic resume/vacancy pairs,
each with a distinct email, phone, and Cyrillic full name. Asserts zero leaks.
"""

from __future__ import annotations

import re
import uuid
from unittest.mock import patch

import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.resume_profile import ResumeProfile
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.models.vacancy_strategy import VacancyStrategy
from app.services import vacancy_strategy as vs_service

# ---------------------------------------------------------------------------
# PII pools — hand-built, deterministic
# ---------------------------------------------------------------------------

_EMAILS = [
    "ivan.petrov@yandex.ru",
    "a.sidorov@mail.ru",
    "marina.k@gmail.com",
    "d.volkov+work@outlook.com",
    "test.user123@rambler.ru",
    "oleg@bk.ru",
    "natasha.r@protonmail.com",
    "petr.777@icloud.com",
    "alexey_dev@yahoo.com",
    "svetlana.m@inbox.ru",
    "dmitry.a@corp.example.com",
    "user42@list.ru",
    "kate.s@tutanota.com",
    "roman.b@fastmail.com",
    "olga.v@zoho.com",
    "mikhail@example.org",
    "anna.k@edu.ru",
    "sergey.l@company.ru",
    "elena.n@work.ru",
    "andrey.p@startup.io",
    "nikita_q@web.de",
    "viktoria.f@pm.me",
    "kostya.r@hey.com",
    "lyudmila.s@aol.com",
    "boris.t@live.ru",
    "daria.u@hmail.com",
    "fyodor.v@online.ru",
    "galina.w@net.ru",
    "igor.x@connect.ru",
    "julia.y@secure.ru",
]

# Phones in various formats — all normalize to 10 significant digits starting with a 3-digit area code
_PHONES = [
    "+7 (916) 111-22-33",
    "+7(499)222-33-44",
    "8 (903) 333-44-55",
    "8(812)444-55-66",
    "+7 916 555-66-77",
    "+7-495-666-77-88",
    "8 800 777-88-99",
    "+7(926)888-99-00",
    "8(977)900-11-22",
    "+7 (985) 012-34-56",
    "+7(915)123-45-67",
    "8(916)234-56-78",
    "+7 903 345-67-89",
    "+7(999)456-78-90",
    "8 (910) 567-89-01",
    "+7(911)678-90-12",
    "8(912)789-01-23",
    "+7 913 890-12-34",
    "+7(914)901-23-45",
    "8 (917) 012-45-56",
    "+7(918)123-56-67",
    "8(919)234-67-78",
    "+7 920 345-78-89",
    "+7(921)456-89-90",
    "8 (922) 567-90-01",
    "+7(923)678-01-12",
    "8(924)789-12-23",
    "+7 925 890-23-34",
    "+7(927)901-34-45",
    "8 (928) 012-56-67",
]

# Russian first+last name pairs
_NAMES = [
    ("Иван", "Петров"),
    ("Алексей", "Сидоров"),
    ("Марина", "Козлова"),
    ("Дмитрий", "Волков"),
    ("Светлана", "Романова"),
    ("Олег", "Белов"),
    ("Наталья", "Михайлова"),
    ("Пётр", "Новиков"),
    ("Екатерина", "Соловьёва"),
    ("Роман", "Борисов"),
    ("Ольга", "Васильева"),
    ("Михаил", "Фёдоров"),
    ("Анна", "Карпова"),
    ("Сергей", "Лебедев"),
    ("Елена", "Никитина"),
    ("Андрей", "Попов"),
    ("Никита", "Кузнецов"),
    ("Виктория", "Фомина"),
    ("Константин", "Рябов"),
    ("Людмила", "Суворова"),
    ("Борис", "Тихонов"),
    ("Дарья", "Ушакова"),
    ("Фёдор", "Виноградов"),
    ("Галина", "Широкова"),
    ("Игорь", "Харитонов"),
    ("Юлия", "Яковлева"),
    ("Владимир", "Захаров"),
    ("Тамара", "Громова"),
    ("Артём", "Щербаков"),
    ("Инна", "Орлова"),
]

_MUST_HAVE_SKILLS_POOL = [
    ["Python", "Docker", "Kubernetes"],
    ["Java", "Spring Boot", "PostgreSQL"],
    ["Go", "gRPC", "Redis"],
    ["React", "TypeScript", "GraphQL"],
    ["Machine Learning", "PyTorch", "MLflow"],
]

_EXPERIENCE_POOL = [
    [{"company": "ООО Рога", "role": "Dev", "highlights": ["Built Python APIs"]}],
    [{"company": "ООО Копыта", "role": "Eng", "highlights": ["Led Java backend"]}],
    [{"company": "Стартап", "role": "SWE", "highlights": ["Wrote Go services"]}],
    [{"company": "Агентство", "role": "Frontend", "highlights": ["Built React apps"]}],
    [{"company": "НИИ", "role": "DS", "highlights": ["Trained ML models"]}],
]


def _digits_only(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def build_synthetic_pair(case_idx: int):
    email = _EMAILS[case_idx % len(_EMAILS)]
    phone = _PHONES[case_idx % len(_PHONES)]
    first_name, last_name = _NAMES[case_idx % len(_NAMES)]
    must_have_skills = _MUST_HAVE_SKILLS_POOL[case_idx % len(_MUST_HAVE_SKILLS_POOL)]
    experience = _EXPERIENCE_POOL[case_idx % len(_EXPERIENCE_POOL)]
    # Inject PII into canonical_text to simulate a raw resume input
    skills = ["Python", "FastAPI", "PostgreSQL"]
    profile_dict = {
        "role_family": "software_engineering",
        "seniority": "middle",
        "seniority_confidence": 0.85,
        "total_experience_years": 3,
        "skills": skills,
        "hard_skills": skills,
        "experience": experience,
    }
    canonical = (
        f"{first_name} {last_name}\n"
        f"Email: {email}\n"
        f"Phone: {phone}\n"
        "Skills: Python, FastAPI, PostgreSQL"
    )
    vp_data = {
        "title": f"Vacancy {case_idx}",
        "must_have_skills": must_have_skills,
        "role_family": "software_engineering",
    }
    return (
        profile_dict,
        canonical,
        vp_data,
        email,
        phone,
        first_name,
        last_name,
    )


@pytest.fixture(scope="session")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.mark.parametrize("case_idx", range(30))
def test_template_mode_strategy_never_leaks_pii(case_idx, db_session):
    """For 30 synthetic resume/vacancy pairs, cover_letter_draft must contain
    zero PII: no literal email, no phone digit sequence, no full Cyrillic name.
    """
    db = db_session
    profile_dict, canonical, vp_data, email, phone, first_name, last_name = build_synthetic_pair(
        case_idx
    )

    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"pii-guard-{case_idx}-{suffix}@example.com",
        hashed_password=hash_password("TestPass123"),
        full_name=f"{first_name} {last_name}",
        is_active=True,
        email_verified=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    resume = Resume(
        user_id=user.id,
        original_filename="cv.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={"target_role": "Dev"},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    rp = ResumeProfile(
        resume_id=resume.id,
        user_id=user.id,
        profile=profile_dict,
        canonical_text=canonical,
        qdrant_collection="test_col",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(rp)
    db.commit()
    db.refresh(rp)

    vac_uid = uuid.uuid4().hex[:12]
    vacancy = Vacancy(
        source="test",
        source_url=f"https://example.com/jobs/pii-{vac_uid}",
        title=f"Vacancy {case_idx}",
        company="TestCo",
        status="indexed",
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)

    vp_row = VacancyProfile(
        vacancy_id=vacancy.id,
        profile=vp_data,
        canonical_text=f"Job: Vacancy {case_idx}\nRequired: "
        + ", ".join(vp_data["must_have_skills"]),
        qdrant_collection="test_vac_col",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(vp_row)
    db.commit()
    db.refresh(vp_row)

    try:
        with patch("app.services.vacancy_strategy.settings") as mock_settings:
            mock_settings.feature_vacancy_strategy_enabled = True
            mock_settings.feature_vacancy_strategy_template_mode_enabled = True
            mock_settings.vacancy_strategy_cache_ttl_days = 30
            mock_settings.openai_api_key = None
            mock_settings.vacancy_strategy_cost_cap_usd_per_day = 1.0
            out = vs_service.compute_strategy(db, resume.id, vacancy.id, user.id)

        text = out.cover_letter_draft

        assert email not in text, (
            f"[CASE {case_idx}] EMAIL LEAK: '{email}' found in cover letter draft"
        )

        phone_digits = _digits_only(phone)
        # Check the last 10 digits (area code + number) in the stripped output
        phone_core = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
        text_digits = _digits_only(text)
        assert phone_core not in text_digits, (
            f"[CASE {case_idx}] PHONE LEAK: digits '{phone_core}' found in cover letter draft"
        )

        full_name = f"{first_name} {last_name}"
        assert full_name not in text, (
            f"[CASE {case_idx}] NAME LEAK: '{full_name}' found in cover letter draft"
        )
    finally:
        from sqlalchemy import delete

        db.execute(delete(VacancyStrategy).where(VacancyStrategy.resume_id == resume.id))
        db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == resume.id))
        db.execute(delete(Resume).where(Resume.id == resume.id))
        db.execute(delete(VacancyProfile).where(VacancyProfile.vacancy_id == vacancy.id))
        db.execute(delete(Vacancy).where(Vacancy.id == vacancy.id))
        db.execute(delete(User).where(User.id == user.id))
        db.commit()
