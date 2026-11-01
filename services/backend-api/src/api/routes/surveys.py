"""Authenticated survey inspection and occurrence-specific resident capabilities."""
import os
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user, require_admin_or_owner
from src.database.session import get_db
from src.models.survey import SurveyInstance, SurveyResident
from src.models.user import User
from src.services import surveys as service
from src.services.review_preview import require_preview_organization

router = APIRouter(tags=['surveys'])


class MaintenanceCompletedEvent(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    event_id: str = Field(min_length=1, max_length=200)
    occurrence_id: str = Field(min_length=1, max_length=200)
    event_type: Literal['maintenance_completed']
    community_id: int = Field(gt=0)
    ticket_id: str = Field(min_length=1, max_length=200)
    request_description: str = Field(min_length=1, max_length=1000)
    completed_at: AwareDatetime
    resident_id: str = Field(min_length=1, max_length=200)
    resident_name: str = Field(min_length=1, max_length=200)
    resident_email: str = Field(max_length=320, pattern=r'^[^@\s]+@[^@\s]+\.invalid$')
    unit_id: str = Field(min_length=1, max_length=200)
    unit_number: str = Field(min_length=1, max_length=100)
    employee_id: str | None = Field(default=None, min_length=1, max_length=200)
    employee_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_simulated: Literal[True]
    resident_opt_out: bool = False

    @field_validator('resident_email')
    @classmethod
    def normalize_email(cls, value):
        return value.lower()


class AnswerSave(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answers: dict[str, Any]


def private_response(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'


def check_origin(request: Request):
    origin = request.headers.get('origin')
    if origin and origin.rstrip('/') != service.public_base_url():
        raise HTTPException(403, 'Use the original survey application to save answers')


def resident_survey(token: str, db):
    if len(token) > 100:
        raise HTTPException(404, 'Survey link not found')
    row = db.query(SurveyInstance).filter_by(token=token).first()
    if row is None:
        raise HTTPException(404, 'Survey link not found')
    return row


@router.get('/api/v1/resident-surveys/{token}')
def load_resident_survey(token: str, response: Response, db: Session = Depends(get_db)):
    private_response(response)
    return service.serialize_survey(resident_survey(token, db))


@router.put('/api/v1/resident-surveys/{token}/draft')
def save_resident_draft(token: str, body: AnswerSave, request: Request, response: Response,
                        db: Session = Depends(get_db)):
    private_response(response); check_origin(request)
    row = resident_survey(token, db)
    try:
        return service.serialize_survey(service.save_answers(db, row, body.answers))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post('/api/v1/resident-surveys/{token}/submit')
def submit_resident_survey(token: str, body: AnswerSave, request: Request, response: Response,
                          db: Session = Depends(get_db)):
    private_response(response); check_origin(request)
    row = resident_survey(token, db)
    try:
        return service.serialize_survey(service.save_answers(db, row, body.answers, final=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post('/api/v1/resident-surveys/{token}/unsubscribe')
def unsubscribe_resident(token: str, request: Request, response: Response,
                         db: Session = Depends(get_db)):
    private_response(response); check_origin(request)
    row = resident_survey(token, db)
    resident = row.occurrence.resident
    # Preserve opt-out even if a later source event gives another resident ID.
    db.query(SurveyResident).filter(SurveyResident.organization_id == row.organization_id,
        or_(SurveyResident.id == resident.id,
            func.lower(SurveyResident.email) == row.occurrence.resident_email.lower())).update(
                {'email_opt_out': True}, synchronize_session=False)
    service.suppress_email(db, row.organization_id, row.occurrence.resident_email)
    db.commit()
    return {'status': 'unsubscribed', 'message': 'Future survey invitations for this community are stopped.'}


@router.post('/api/v1/surveys/simulate', dependencies=[Depends(require_admin_or_owner)])
def simulate_maintenance_event(body: MaintenanceCompletedEvent, response: Response,
                               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    private_response(response)
    require_preview_organization(user.organization_id)
    if os.getenv('BOOMSAY_SURVEY_SIMULATION', '').lower() != 'true':
        raise HTTPException(404, 'Survey event simulation is not enabled')
    if body.community_id != user.organization_id:
        raise HTTPException(403, 'The event community must match your authorized community')
    try:
        return service.serialize_survey(service.ingest_simulated_event(db, body), manager=True)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None


@router.get('/api/v1/surveys')
def list_surveys(response: Response, page: int = Query(default=1, ge=1),
                 page_size: int = Query(default=20, ge=1, le=100),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    private_response(response)
    require_preview_organization(user.organization_id)
    query = db.query(SurveyInstance).filter_by(organization_id=user.organization_id)
    total = query.count()
    rows = query.order_by(SurveyInstance.created_at.desc(), SurveyInstance.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {'surveys': [service.serialize_survey(row, manager=True) for row in rows], 'total': total}


@router.get('/api/v1/surveys/{public_id}')
def get_survey(public_id: UUID, response: Response, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    private_response(response)
    require_preview_organization(user.organization_id)
    row = db.query(SurveyInstance).filter_by(public_id=str(public_id), organization_id=user.organization_id).first()
    if row is None:
        raise HTTPException(404, 'Survey not found')
    return service.serialize_survey(row, manager=True)
