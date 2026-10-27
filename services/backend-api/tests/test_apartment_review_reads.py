"""Saved apartment review reads and sorting, without analysis or provider calls."""

import pytest
from datetime import date


@pytest.mark.parametrize('setting,expected', [(None, 503), ('invalid', 503), ('0', 503), ('999999', 403)])
def test_preview_requires_explicit_authorized_binding(client, auth_headers, monkeypatch, setting, expected):
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    if setting is None:
        monkeypatch.delenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', raising=False)
    else:
        monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', setting)
    for path in ('/api/v1/feedback/preview-community', '/api/v1/feedback/', '/api/v1/feedback/1'):
        assert client.get(path, headers=auth_headers).status_code == expected


def test_preview_binding_returns_lake_house_and_saved_reviews(client, auth_headers, test_organization, saved_reviews, monkeypatch):
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', str(test_organization.id))
    response = client.get('/api/v1/feedback/preview-community', headers=auth_headers)
    assert response.json() == {'organization_id': test_organization.id, 'name': 'Lake House Apartments'}
    assert client.get('/api/v1/feedback/', headers=auth_headers).json()['total'] == 3


def test_preview_community_is_not_exposed_when_disabled(client, auth_headers, monkeypatch):
    monkeypatch.delenv('BOOMSAY_REVIEW_PREVIEW', raising=False)
    assert client.get('/api/v1/feedback/preview-community', headers=auth_headers).status_code == 404

from src.models.feedback import FeedbackItem
from src.models.organization import Organization


@pytest.fixture
def saved_reviews(db, test_organization):
    result = {
        "final_result": {
            "method": "ai_model",
            "sentiment": "mixed",
            "topics": [{
                "name": "Staff & customer service",
                "sentiment": "mixed",
                "quotations": [
                    {"text": "Helpful staff.", "sentiment": "positive"},
                    {"text": "Later rude staff.", "sentiment": "negative"},
                ],
            }],
        },
    }
    reviews = [
        FeedbackItem(organization_id=test_organization.id, text="Helpful staff. Later rude staff.",
                     source="apartment_review_ai", star_rating=2, sentiment_label="mixed",
                     review_date=date(2026, 10, 20), source_external_id="synthetic-review-a", apartment_analysis=result),
        FeedbackItem(organization_id=test_organization.id, text="",
                     source="apartment_review_ai", star_rating=4, sentiment_label="positive",
                     review_date=date(2026, 9, 1), source_external_id="synthetic-review-b",
                     apartment_analysis={"final_result": {
                         "method": "ai_model", "sentiment": "positive", "topics": [],
                     }}),
        FeedbackItem(organization_id=test_organization.id, text="Noisy apartment.",
                     source="apartment_review_ai", star_rating=2, sentiment_label="negative",
                     source_external_id="synthetic-review-c"),
    ]
    other_org = Organization(name="Other test community", plan="pro")
    db.add(other_org)
    db.flush()
    outsider = FeedbackItem(organization_id=other_org.id, text="Other community's review.",
                            source="apartment_review_ai", star_rating=1, sentiment_label="negative",
                            source_external_id="synthetic-outside", apartment_analysis=result)
    db.add_all([*reviews, outsider])
    db.commit()
    return reviews, outsider


@pytest.mark.parametrize("sort_by,sort_order,indices", [
    ("star_rating", "asc", [0, 2, 1]),
    ("star_rating", "desc", [1, 2, 0]),
    ("sentiment_label", "asc", [0, 2, 1]),
    ("sentiment_label", "desc", [1, 2, 0]),
    ("review_date", "asc", [1, 0, 2]),
    ("review_date", "desc", [0, 1, 2]),
    ("id", "asc", [0, 1, 2]),
    ("id", "desc", [2, 1, 0]),
])
def test_sort_and_paginate_only_authenticated_organization(
    client, auth_headers, saved_reviews, sort_by, sort_order, indices,
):
    reviews, outsider = saved_reviews
    ids = []
    for page in (1, 2, 3):
        response = client.get("/api/v1/feedback/", headers=auth_headers, params={
            "sort_by": sort_by, "sort_order": sort_order, "page_size": 1, "page": page,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        ids.extend(item["id"] for item in data["items"])
    assert ids == [reviews[i].id for i in indices]
    assert outsider.id not in ids


def test_saved_fields_and_rating_only_text_survive_list_and_detail(
    client, auth_headers, saved_reviews,
):
    reviews, _ = saved_reviews
    response = client.get("/api/v1/feedback/", headers=auth_headers)
    assert response.status_code == 200
    listed = {item["id"]: item for item in response.json()["items"]}
    for review in reviews:
        detail = client.get(f"/api/v1/feedback/{review.id}", headers=auth_headers)
        assert detail.status_code == 200
        for item in (listed[review.id], detail.json()):
            assert item["review_date"] == (review.review_date.isoformat() if review.review_date else None)
            assert item["text"] == review.text
            assert item["star_rating"] == review.star_rating
            assert item["source_external_id"] == review.source_external_id
            assert item["apartment_analysis"] == review.apartment_analysis


def test_other_organization_detail_is_not_accessible(client, auth_headers, saved_reviews):
    _, outsider = saved_reviews
    response = client.get(f"/api/v1/feedback/{outsider.id}", headers=auth_headers)
    assert response.status_code == 404


def test_mixed_sentiment_filter_is_distinct(client, auth_headers, saved_reviews):
    reviews, _ = saved_reviews
    response = client.get("/api/v1/feedback/", headers=auth_headers, params={"sentiment": "mixed"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [reviews[0].id]


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_saved_reviews_require_authentication(client, saved_reviews, headers):
    reviews, _ = saved_reviews
    for path in ("/api/v1/feedback/", f"/api/v1/feedback/{reviews[0].id}"):
        assert client.get(path, headers=headers).status_code in (401, 403)


def test_organization_scope_comes_from_user_record(client, test_user, saved_reviews):
    from src.api.auth import create_access_token

    reviews, outsider = saved_reviews
    # An old/mismatched organization claim must not change the user's DB scope.
    token = create_access_token({
        "user_id": test_user.id, "organization_id": outsider.organization_id, "role": test_user.role,
    })
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/feedback/", headers=headers)
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == {review.id for review in reviews}
    assert client.get(f"/api/v1/feedback/{outsider.id}", headers=headers).status_code == 404
