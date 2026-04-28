"""One-shot: normalize all vacancy_profiles.domains and User.preferred_domains
to canonical slugs. Idempotent — safe to re-run.

Usage:
    docker compose exec -T backend python -m app.scripts.normalize_existing_domains
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User
from app.models.vacancy_profile import VacancyProfile
from app.services.domain_taxonomy import normalize_domains


def main() -> None:
    db = SessionLocal()
    try:
        # ----- vacancy_profiles -----
        vp_count = 0
        vp_changed = 0
        for vp in db.scalars(select(VacancyProfile)):
            vp_count += 1
            profile = dict(vp.profile or {})
            raw = profile.get("domains")
            if not isinstance(raw, list):
                continue
            normalized = normalize_domains(raw)
            if normalized != raw:
                profile["domains"] = normalized
                vp.profile = profile
                vp_changed += 1
        print(f"vacancy_profiles: scanned={vp_count} updated={vp_changed}")

        # ----- users -----
        u_count = 0
        u_changed = 0
        for u in db.scalars(select(User)):
            u_count += 1
            raw = list(u.preferred_domains or [])
            normalized = normalize_domains(raw)
            if normalized != raw:
                u.preferred_domains = normalized
                u_changed += 1
        print(f"users: scanned={u_count} updated={u_changed}")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
