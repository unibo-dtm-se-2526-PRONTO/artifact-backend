"""Tests for the questions endpoints (FR6, FR7; US2a-US2c).

A student asks a question about an office, gets back the best-matching FAQ, if
any, and says whether it answered them. Asking runs the full-text search, so
the tests that reach it are marked `postgres`; the ones that stop at
validation, and all of resolving, run on SQLite too.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from faq.models import Faq, Inquiry
from pronto.enums import OfficeCode

QUESTIONS_URL = "/api/questions/"


def resolve_url(inquiry_id):
    return f"{QUESTIONS_URL}{inquiry_id}/resolve/"


@pytest.fixture
def certificate(db):
    return Faq.objects.create(
        office_code=OfficeCode.ADMIN_OFFICE,
        question_it="Come richiedo un certificato di iscrizione?",
        question_en="How do I request a certificate of enrolment?",
        answer_it="Dal portale Studenti Online, sezione Certificati.",
        answer_en="From the Studenti Online portal, Certificates section.",
    )


@pytest.fixture
def internship(db):
    return Faq.objects.create(
        office_code=OfficeCode.INTERNSHIPS,
        question_it="Come attivo un tirocinio curriculare?",
        question_en="How do I start a curricular internship?",
        answer_it="Compilando il progetto formativo su AlmaLaurea.",
        answer_en="By filling in the training project on AlmaLaurea.",
    )


def ask(client, office, question, **params):
    query = "&".join(f"{key}={value}" for key, value in params.items())
    url = f"{QUESTIONS_URL}?{query}" if query else QUESTIONS_URL
    return client.post(url, {"office": office, "question": question}, format="json")


# Asking


@pytest.mark.postgres
@pytest.mark.django_db
def test_asking_returns_the_matching_faq(student_client, certificate):
    response = ask(
        student_client,
        OfficeCode.ADMIN_OFFICE,
        "Come richiedo il certificato di iscrizione?",
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    inquiry = Inquiry.objects.get()
    assert body == {
        "id": str(inquiry.id),
        "office": OfficeCode.ADMIN_OFFICE,
        "language": "it",
        "match": {
            "faq": {
                "id": certificate.id,
                "question": certificate.question_it,
                "answer": certificate.answer_it,
            },
            "office": OfficeCode.ADMIN_OFFICE,
            "score": pytest.approx(inquiry.score),
        },
        "office_reassigned": False,
        "resolved": False,
    }


@pytest.mark.postgres
@pytest.mark.django_db
def test_asking_records_the_question_and_its_match(student_client, certificate):
    ask(student_client, OfficeCode.ADMIN_OFFICE, "certificato di iscrizione")

    inquiry = Inquiry.objects.get()
    assert inquiry.office_code == OfficeCode.ADMIN_OFFICE
    assert inquiry.text == "certificato di iscrizione"
    assert inquiry.language == "it"
    assert inquiry.matched_faq == certificate
    assert inquiry.score > 0
    assert inquiry.resolved is False


@pytest.mark.postgres
@pytest.mark.django_db
def test_asking_in_english_searches_and_answers_in_english(student_client, certificate):
    response = ask(
        student_client, OfficeCode.ADMIN_OFFICE, "enrolment certificates", lang="en"
    )

    body = response.json()
    assert body["language"] == "en"
    assert body["match"]["faq"]["question"] == certificate.question_en
    assert body["match"]["faq"]["answer"] == certificate.answer_en


@pytest.mark.postgres
@pytest.mark.django_db
def test_an_answer_from_another_office_says_so(student_client, certificate, internship):
    response = ask(student_client, OfficeCode.ADMIN_OFFICE, "Come attivo il tirocinio?")

    body = response.json()
    assert body["office"] == OfficeCode.ADMIN_OFFICE
    assert body["match"]["office"] == OfficeCode.INTERNSHIPS
    assert body["match"]["faq"]["id"] == internship.id
    assert body["office_reassigned"] is True


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_question_without_a_match_is_still_recorded(student_client, certificate):
    response = ask(
        student_client, OfficeCode.ADMIN_OFFICE, "Dove parcheggio la bicicletta?"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["match"] is None
    assert response.json()["office_reassigned"] is False
    inquiry = Inquiry.objects.get()
    assert inquiry.matched_faq is None
    assert inquiry.score is None


@pytest.mark.django_db
def test_asking_requires_a_token(certificate):
    response = ask(APIClient(), OfficeCode.ADMIN_OFFICE, "certificato")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not Inquiry.objects.exists()


@pytest.mark.django_db
def test_only_students_ask(employee_client, certificate):
    response = ask(employee_client, OfficeCode.ADMIN_OFFICE, "certificato")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Inquiry.objects.exists()


@pytest.mark.django_db
def test_asking_about_an_unknown_office_is_refused(student_client):
    response = ask(student_client, "CANTEEN", "certificato")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "office" in response.json()
    assert not Inquiry.objects.exists()


@pytest.mark.parametrize("question", ["", "   "])
@pytest.mark.django_db
def test_an_empty_question_is_refused(student_client, question):
    response = ask(student_client, OfficeCode.ADMIN_OFFICE, question)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "question" in response.json()


@pytest.mark.django_db
def test_a_missing_question_is_refused(student_client):
    response = student_client.post(
        QUESTIONS_URL, {"office": OfficeCode.ADMIN_OFFICE}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "question" in response.json()


@pytest.mark.django_db
def test_a_question_too_long_is_refused(student_client):
    response = ask(student_client, OfficeCode.ADMIN_OFFICE, "a" * 1001)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "question" in response.json()


@pytest.mark.django_db
def test_asking_in_an_unsupported_language_is_refused(student_client):
    response = ask(student_client, OfficeCode.ADMIN_OFFICE, "certificato", lang="de")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "lang" in response.json()
    assert not Inquiry.objects.exists()


# Resolving


@pytest.fixture
def answered(certificate):
    return Inquiry.objects.create(
        office_code=OfficeCode.ADMIN_OFFICE,
        text="Come chiedo il certificato di iscrizione?",
        language="en",
        matched_faq=certificate,
        score=0.5,
    )


@pytest.fixture
def unanswered(db):
    return Inquiry.objects.create(
        office_code=OfficeCode.ADMIN_OFFICE,
        text="Dove parcheggio la bicicletta?",
        language="it",
    )


@pytest.mark.django_db
def test_resolving_marks_the_question_answered(student_client, answered, certificate):
    response = student_client.post(resolve_url(answered.id))

    assert response.status_code == status.HTTP_200_OK
    # Read back in the language the question was asked in.
    assert response.json() == {
        "id": str(answered.id),
        "office": OfficeCode.ADMIN_OFFICE,
        "language": "en",
        "match": {
            "faq": {
                "id": certificate.id,
                "question": certificate.question_en,
                "answer": certificate.answer_en,
            },
            "office": OfficeCode.ADMIN_OFFICE,
            "score": 0.5,
        },
        "office_reassigned": False,
        "resolved": True,
    }
    answered.refresh_from_db()
    assert answered.resolved is True


@pytest.mark.django_db
def test_resolving_twice_is_harmless(student_client, answered):
    student_client.post(resolve_url(answered.id))
    response = student_client.post(resolve_url(answered.id))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["resolved"] is True


@pytest.mark.django_db
def test_a_question_without_a_suggestion_cannot_be_resolved(student_client, unanswered):
    response = student_client.post(resolve_url(unanswered.id))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    unanswered.refresh_from_db()
    assert unanswered.resolved is False


@pytest.mark.django_db
def test_resolving_an_unknown_question_is_not_found(student_client):
    response = student_client.post(resolve_url(uuid.uuid4()))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_resolving_requires_a_token(answered):
    response = APIClient().post(resolve_url(answered.id))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_only_students_resolve(employee_client, answered):
    response = employee_client.post(resolve_url(answered.id))

    assert response.status_code == status.HTTP_403_FORBIDDEN
