"""Fictional pre-existing review/settings fixture; never creates survey answers."""
import hashlib
import json
import sys
from datetime import date
from src.database.session import SessionLocal
from src.models.feedback import FeedbackItem
from src.models.user import User
from src.survey_demo import demo_community

with SessionLocal() as db:
    community = demo_community(db)  # Refuse any non-demo database.
    if sys.argv[1] == 'seed':
        if not db.query(FeedbackItem).filter_by(source_external_id='full-stack-review-sentinel').first():
            db.add(FeedbackItem(organization_id=community.id, source='apartment_review_ai',
                source_external_id='full-stack-review-sentinel', review_date=date(2026, 10, 20),
                text='Fictional original review: the staff were helpful.', star_rating=4,
                apartment_analysis={'final_result': {'method': 'ai_model', 'sentiment': 'positive',
                    'topics': [{'name': 'Staff', 'sentiment': 'positive', 'quotations': [
                        {'text': 'the staff were helpful.', 'sentiment': 'positive'}]}]}}))
            db.commit()
    user = db.query(User).one()
    reviews = [(r.id, r.text, r.star_rating, r.review_date.isoformat(), r.apartment_analysis)
               for r in db.query(FeedbackItem).filter_by(source_external_id='full-stack-review-sentinel')]
    assert len(reviews) == 1
    assert reviews[0][1:4] == ('Fictional original review: the staff were helpful.', 4, '2026-10-20')
    assert reviews[0][4]['final_result']['topics'][0]['quotations'][0]['text'] == 'the staff were helpful.'
    assert community.ai_analysis_enabled is False and user.ask_genius_default_period is None
    from src.api.auth import verify_password
    assert verify_password('fictional-survey-demo-login', user.password_hash)
    source = {'community': [community.id, community.name, community.plan, community.ai_analysis_enabled],
              'user': [user.id, user.email, user.role, user.password_hash, user.ask_genius_default_period],
              'reviews': reviews}
    print(json.dumps({'preservation_sha256': hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(),
                      'review_count': len(reviews), 'community_id': community.id}))
