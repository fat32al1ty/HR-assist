import threading
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.users import update_preferences
from app.schemas.user import UserPreferencesUpdate, UserRead
from app.services.domain_taxonomy import all_canonical_slugs

router = APIRouter()

# In-process suggestion cache: {cache_key: (expires_at, results)}
_suggestions_cache: dict[str, tuple[float, list[dict]]] = {}
_suggestions_cache_lock = threading.Lock()
_SUGGESTIONS_CACHE_TTL = 300  # 5 minutes


class SuggestionItem(BaseModel):
    value: str
    frequency: int
    display_name: str | None = None


class SuggestionsResponse(BaseModel):
    suggestions: list[SuggestionItem]


@router.get("/preferences/suggestions", response_model=SuggestionsResponse)
def get_preference_suggestions(
    type: Annotated[Literal["role", "domain"], Query()] = "role",
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuggestionsResponse:
    cache_key = f"{type}:{(q or '').lower().strip()}:{limit}"
    now = time.monotonic()
    with _suggestions_cache_lock:
        entry = _suggestions_cache.get(cache_key)
        if entry is not None and entry[0] > now:
            return SuggestionsResponse(suggestions=[SuggestionItem(**s) for s in entry[1]])

    prefix = (q or "").strip().lower()
    if type == "role":
        # roles live in vacancy_profiles.profile JSON under "role" or "role_family"
        # Cast profile::jsonb because the column is JSON (not JSONB); JSON does not
        # support the ? operator or jsonb_* functions.  The per-row cast is cheap
        # enough for a typeahead — we avoid a migration to keep this change minimal.
        raw = db.execute(
            text(
                """
                SELECT val, COUNT(*) AS freq
                FROM vacancy_profiles,
                     jsonb_array_elements_text(
                         CASE
                             WHEN (profile::jsonb) ? 'role'
                               AND jsonb_typeof((profile::jsonb)->'role') = 'string'
                             THEN jsonb_build_array((profile::jsonb)->>'role')
                             WHEN (profile::jsonb) ? 'role_family'
                               AND jsonb_typeof((profile::jsonb)->'role_family') = 'string'
                             THEN jsonb_build_array((profile::jsonb)->>'role_family')
                             ELSE '[]'::jsonb
                         END
                     ) AS val
                WHERE val <> ''
                  AND (:prefix = '' OR lower(val) LIKE :like_prefix)
                GROUP BY val
                ORDER BY freq DESC
                LIMIT :lim
                """
            ),
            {"prefix": prefix, "like_prefix": prefix + "%", "lim": limit},
        ).fetchall()
    else:
        # domains: return canonical slugs from taxonomy (display_name filtered by prefix)
        matched = [
            {"value": slug, "frequency": 0, "display_name": display}
            for slug, display in all_canonical_slugs()
            if not prefix or display.lower().startswith(prefix) or slug.startswith(prefix)
        ]
        raw_domain = matched[:limit]
        results = raw_domain
        with _suggestions_cache_lock:
            _suggestions_cache[cache_key] = (now + _SUGGESTIONS_CACHE_TTL, results)
        return SuggestionsResponse(suggestions=[SuggestionItem(**s) for s in results])

    results = [{"value": row[0], "frequency": int(row[1])} for row in raw]
    with _suggestions_cache_lock:
        _suggestions_cache[cache_key] = (now + _SUGGESTIONS_CACHE_TTL, results)
    return SuggestionsResponse(suggestions=[SuggestionItem(**s) for s in results])


@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me/preferences", response_model=UserRead)
def patch_me_preferences(
    payload: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    fields = payload.model_dump(exclude_unset=True)
    clear_home_city = "home_city" in fields and fields["home_city"] is None
    return update_preferences(
        db,
        current_user,
        preferred_work_format=fields.get("preferred_work_format"),
        relocation_mode=fields.get("relocation_mode"),
        home_city=fields.get("home_city"),
        preferred_titles=fields.get("preferred_titles"),
        preferred_domains=fields.get("preferred_domains"),
        clear_home_city=clear_home_city,
        expected_salary_min=fields.get("expected_salary_min"),
        expected_salary_max=fields.get("expected_salary_max"),
        expected_salary_currency=fields.get("expected_salary_currency"),
    )
