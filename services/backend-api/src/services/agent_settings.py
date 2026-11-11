"""Settings used by both the onboarding UI and the actual community workflows."""
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.agent_settings import CommunityAgentSettings
from src.models.organization import Organization
from src.models.user import User
from src.services.survey_catalog import EVENT_LABELS


class SettingsInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, strict=True)


class ReviewSettings(SettingsInput):
    community_name: str = Field(min_length=1, max_length=200)
    public_email: str = Field(max_length=254)
    public_phone: str = Field(max_length=48)
    facts: str = Field(max_length=1500)
    tone: Literal['warm', 'professional', 'concise']
    signature: str = Field(max_length=160)
    praise_guidance: str = Field(max_length=500)
    complaint_guidance: str = Field(max_length=500)
    mode: Literal['approval', 'automatic']
    hold_at_or_below: int = Field(ge=0, le=5)
    hold_topics: list[Literal['safety', 'billing', 'legal', 'staff_allegations']] = Field(max_length=4)

    @field_validator('public_email')
    @classmethod
    def public_contact_is_email(cls, value):
        return str(TypeAdapter(EmailStr).validate_python(value)) if value else ''

    @field_validator('hold_topics')
    @classmethod
    def unique_topics(cls, value):
        return list(dict.fromkeys(value))


class ScheduleEntry(SettingsInput):
    enabled: bool
    delay_hours: Literal[0, 24, 48, 72]


class SurveySettings(SettingsInput):
    schedule: dict[str, ScheduleEntry]
    reminder_hours: Literal[24, 48, 72] | None
    flag_low_ratings: bool
    flag_unresolved: bool

    @field_validator('schedule')
    @classmethod
    def require_all_seven_surveys(cls, value):
        if set(value) != set(EVENT_LABELS):
            raise ValueError('Confirm a schedule for each of the seven survey types.')
        return value


T = TypeVar('T', bound=SettingsInput)


class SectionState(BaseModel, Generic[T]):
    configured: bool
    version: int
    values: T


class SectionUpdate(SettingsInput, Generic[T]):
    version: int = Field(ge=0)
    values: T


def review_defaults(org: Organization) -> ReviewSettings:
    return ReviewSettings(
        community_name=org.name[:200], public_email='', public_phone='', facts='', tone='professional',
        signature=f'The {org.name} team'[:160], praise_guidance='', complaint_guidance='',
        mode='approval', hold_at_or_below=3, hold_topics=['safety', 'billing', 'legal', 'staff_allegations'],
    )


def survey_defaults() -> SurveySettings:
    return SurveySettings(
        schedule={kind: ScheduleEntry(enabled=True, delay_hours=0) for kind in EVENT_LABELS},
        reminder_hours=None, flag_low_ratings=True, flag_unresolved=True,
    )


def review_section(db: Session, org: Organization) -> SectionState[ReviewSettings]:
    row = db.get(CommunityAgentSettings, (org.id, 'reviews'))
    return SectionState[ReviewSettings](
        configured=bool(row), version=row.version if row else 0,
        values=ReviewSettings.model_validate(row.settings) if row else review_defaults(org),
    )


def survey_section(db: Session, organization_id: int) -> SectionState[SurveySettings]:
    row = db.get(CommunityAgentSettings, (organization_id, 'surveys'))
    return SectionState[SurveySettings](
        configured=bool(row), version=row.version if row else 0,
        values=SurveySettings.model_validate(row.settings) if row else survey_defaults(),
    )


def survey_settings(db: Session, organization_id: int) -> SurveySettings:
    return survey_section(db, organization_id).values


class SettingsConflict(Exception):
    pass


def confirm_section(db: Session, user: User, section: Literal['reviews', 'surveys'], data: SectionUpdate):
    """Compare-and-set each tab independently, including its first confirmation."""
    values = data.values.model_dump(mode='json')
    revision = data.version + 1
    if data.version == 0:
        db.add(CommunityAgentSettings(organization_id=user.organization_id, section=section,
                                      settings=values, version=revision, updated_by=user.id))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            # Concurrent first confirmations conflict on the same unique key.
            if db.get(CommunityAgentSettings, (user.organization_id, section)) is not None:
                raise SettingsConflict from None
            raise
    else:
        changed = db.execute(update(CommunityAgentSettings).where(
            CommunityAgentSettings.organization_id == user.organization_id,
            CommunityAgentSettings.section == section,
            CommunityAgentSettings.version == data.version,
        ).values(settings=values, version=revision, updated_by=user.id, updated_at=func.now()))
        if changed.rowcount != 1:
            db.rollback()
            raise SettingsConflict
    if section == 'surveys':
        # Apply pauses in the same transaction as confirmation so canceled work
        # cannot silently resume if the manager re-enables it later.
        from src.services.survey_schedule import cancel_paused_simulations
        cancel_paused_simulations(db, user.organization_id, data.values)
    db.commit()
    return {'configured': True, 'version': revision, 'values': values}
