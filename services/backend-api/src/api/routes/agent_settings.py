"""Read and confirm a single community's review and survey preferences."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user, require_community_manager
from src.database.session import get_db
from src.models.user import User
from src.services import agent_settings as settings
from src.services.review_preview import require_preview_organization

router = APIRouter(prefix='/api/v1/agent-settings', tags=['agent-settings'])


class AgentSettingsOut(BaseModel):
    community_name: str
    can_edit: bool
    reviews: settings.SectionState[settings.ReviewSettings]
    surveys: settings.SectionState[settings.SurveySettings]


@router.get('', response_model=AgentSettingsOut)
def current_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_preview_organization(user.organization_id)
    return AgentSettingsOut(
        community_name=user.organization.name, can_edit=user.role in {'admin', 'owner'},
        reviews=settings.review_section(db, user.organization), surveys=settings.survey_section(db, user.organization_id),
    )


def save_section(user, db, key, payload):
    require_preview_organization(user.organization_id)
    try:
        return settings.confirm_section(db, user, key, payload)
    except settings.SettingsConflict:
        raise HTTPException(409, 'Another manager updated this tab. Load the current settings before saving.') from None


@router.put('/reviews', response_model=settings.SectionState[settings.ReviewSettings])
def save_reviews(payload: settings.SectionUpdate[settings.ReviewSettings], user: User = Depends(require_community_manager),
                 db: Session = Depends(get_db)):
    return save_section(user, db, 'reviews', payload)


@router.put('/surveys', response_model=settings.SectionState[settings.SurveySettings])
def save_surveys(payload: settings.SectionUpdate[settings.SurveySettings], user: User = Depends(require_community_manager),
                 db: Session = Depends(get_db)):
    return save_section(user, db, 'surveys', payload)
