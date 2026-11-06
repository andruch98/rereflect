"""Management of public review drafts, independent from private support responses."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user, require_community_manager
from src.database.session import get_db
from src.models.review_reply import ReviewReply
from src.models.user import User
from src.services.agent_settings import ReviewSettings, review_section
from src.services.review_preview import require_preview_organization
from src.services.review_reply_writer import approval_policy, write_reply
from src.services.review_replies import change_draft, draft, scoped_review, view

router = APIRouter(prefix='/api/v1/review-replies', tags=['review-replies'])


class ReplyEdit(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=4500)


class ReplyApproval(ReplyEdit):
    text: str | None = Field(default=None, min_length=1, max_length=4500)


@router.post('/preview')
async def preview(settings: ReviewSettings, user: User = Depends(require_community_manager), db: Session = Depends(get_db)):
    require_preview_organization(user.organization_id)
    examples = []
    for stars, review in ((5, 'The leasing team made move-in easy.'),
                          (4, 'I enjoy living here, but the broken lock on the side entrance feels unsafe.')):
        try:
            text, method, _ = await write_reply(db, user.organization_id, settings, review, stars)
        except Exception:
            raise HTTPException(503, 'The preview could not be generated. Check the AI connection and try again.') from None
        status, reason = approval_policy(settings, review, stars)
        examples.append({'review_text': review, 'star_rating': stars, 'text': text,
                         'status': status, 'reason': reason, 'generation_method': method})
    return {'examples': examples, 'publishing_connected': False}


@router.get('/{review_id}')
def detail(review_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    scoped_review(db, user.organization_id, review_id)
    return view(db.get(ReviewReply, review_id), review_id, review_section(db, user.organization).version)


@router.post('/{review_id}/draft')
async def prepare(review_id: int, user: User = Depends(require_community_manager), db: Session = Depends(get_db)):
    return await draft(db, user.organization, review_id, user.id)


@router.put('/{review_id}')
def edit(review_id: int, body: ReplyEdit, user: User = Depends(require_community_manager), db: Session = Depends(get_db)):
    return change_draft(db, user, review_id, body.version, body.text, False)


@router.post('/{review_id}/approve')
def approve(review_id: int, body: ReplyApproval, user: User = Depends(require_community_manager), db: Session = Depends(get_db)):
    return change_draft(db, user, review_id, body.version, body.text, True)
