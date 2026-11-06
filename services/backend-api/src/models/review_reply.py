from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from .base import Base


class ReviewReply(Base):
    """One manager-facing response per original apartment review."""
    __tablename__ = 'review_replies'
    __table_args__ = (CheckConstraint(
        "status IN ('pending_approval','approved','published','failed')",
        name='ck_review_replies_status',
    ),)

    review_id = Column(Integer, ForeignKey('feedback_items.id', ondelete='CASCADE'), primary_key=True)
    status = Column(String(20), nullable=False)
    text = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    generation_method = Column(String(12))
    generation_usage = Column(JSON)
    settings_version = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    approved_by = Column(String(320))
    approved_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    error = Column(Text)
