from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.users import update_preferences
from app.schemas.user import UserPreferencesUpdate, UserRead

router = APIRouter()


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
        clear_home_city=clear_home_city,
    )
