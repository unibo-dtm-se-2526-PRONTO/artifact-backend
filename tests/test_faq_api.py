"""Tests for the public FAQ endpoints.

The FAQ slice replaces the phone helpdesk it automates, so reading it must not
require an account: these tests hit the endpoints with an anonymous client on
purpose.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from faq.models import Faq
from pronto.enums import OfficeCode

FAQS_URL = "/api/faqs/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def faq(db):
    return Faq.objects.create(
        office_code=OfficeCode.ADMIN_OFFICE,
        question_it="Come richiedo un certificato di iscrizione?",
        question_en="How do I request a certificate of enrolment?",
        answer_it="Dal portale Studenti Online, sezione Certificati.",
        answer_en="From the Studenti Online portal, Certificates section.",
    )


@pytest.mark.django_db
def test_faq_list_is_readable_without_a_token(client, faq):
    response = client.get(FAQS_URL)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_faq_list_answers_in_italian_by_default(client, faq):
    response = client.get(FAQS_URL)

    assert response.json() == [
        {
            "id": faq.id,
            "office_code": OfficeCode.ADMIN_OFFICE,
            "question": faq.question_it,
            "answer": faq.answer_it,
        }
    ]


@pytest.mark.django_db
def test_faq_list_answers_in_english_when_asked(client, faq):
    response = client.get(FAQS_URL, {"lang": "en"})

    assert response.json()[0]["question"] == faq.question_en
    assert response.json()[0]["answer"] == faq.answer_en


@pytest.mark.django_db
def test_faq_list_never_exposes_the_per_language_fields(client, faq):
    response = client.get(FAQS_URL)

    assert "question_it" not in response.json()[0]
    assert "question_en" not in response.json()[0]


@pytest.mark.django_db
def test_faq_list_rejects_an_unsupported_language(client, faq):
    response = client.get(FAQS_URL, {"lang": "de"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_faq_list_hides_inactive_faqs(client, faq):
    faq.is_active = False
    faq.save()

    response = client.get(FAQS_URL)

    assert response.json() == []


@pytest.mark.django_db
def test_faq_list_can_be_filtered_by_office(client, faq):
    other = Faq.objects.create(
        office_code=OfficeCode.INTERNSHIPS,
        question_it="Come attivo un tirocinio?",
        question_en="How do I start an internship?",
        answer_it="Compilando il progetto formativo.",
        answer_en="By filling in the training project.",
    )

    response = client.get(FAQS_URL, {"office": OfficeCode.INTERNSHIPS})

    assert [item["id"] for item in response.json()] == [other.id]


@pytest.mark.django_db
def test_faq_list_rejects_an_unknown_office_code(client, faq):
    response = client.get(FAQS_URL, {"office": "CANTEEN"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_faq_detail_returns_one_faq(client, faq):
    response = client.get(f"{FAQS_URL}{faq.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["question"] == faq.question_it


@pytest.mark.django_db
def test_faq_detail_honours_the_language_parameter(client, faq):
    response = client.get(f"{FAQS_URL}{faq.id}/", {"lang": "en"})

    assert response.json()["question"] == faq.question_en


@pytest.mark.django_db
def test_faq_detail_hides_an_inactive_faq(client, faq):
    faq.is_active = False
    faq.save()

    response = client.get(f"{FAQS_URL}{faq.id}/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
