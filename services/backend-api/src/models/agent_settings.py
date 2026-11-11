"""One manager-confirmed configuration for each community and workflow."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON, String, func

from .base import Base


class CommunityAgentSettings(Base):
    __tablename__ = 'community_agent_settings'
    __table_args__ = (CheckConstraint("section IN ('reviews', 'surveys')", name='ck_agent_settings_section'),)

    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True)
    section = Column(String(12), primary_key=True)
    version = Column(Integer, nullable=False)
    settings = Column(JSON, nullable=False)
    updated_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
