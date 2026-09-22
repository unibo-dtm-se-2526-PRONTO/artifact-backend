"""Tests for the office and availability endpoints."""

import pytest
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient

from booking.models import Office
from tests.conftest import make_employee, slot_at
from pronto.enums import OfficeCode

OFFICES_URL = "/api/offices/"


def availability_url(code):
    return f"{OFFICES_URL}{code}/availability/"


@pytest.fixture
def inactive_office(db):
    return Office.objects.create(
        code=OfficeCode.INTERNSHIPS,
        name_it="Tirocini",
        name_en="Internships",
        contact_email="tirocini@unibo.it",
        is_active=False,
    )


@pytest.mark.django_db
def test_office_list_requires_a_token(office):
    response = APIClient().get(OFFICES_URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_office_list_answers_in_italian_by_default(student_client, office):
    response = student_client.get(OFFICES_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [
        {
            "code": OfficeCode.GUIDANCE,
            "name": office.name_it,
            "contact_email": office.contact_email,
            "slot_duration_minutes": office.slot_duration_minutes,
        }
    ]


@pytest.mark.django_db
def test_office_list_answers_in_english_when_asked(student_client, office):
    response = student_client.get(OFFICES_URL, {"lang": "en"})

    assert response.json()[0]["name"] == office.name_en


@pytest.mark.django_db
def test_office_list_rejects_an_unsupported_language(student_client, office):
    response = student_client.get(OFFICES_URL, {"lang": "de"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_office_list_hides_inactive_offices(student_client, office, inactive_office):
    response = student_client.get(OFFICES_URL)

    assert [item["code"] for item in response.json()] == [OfficeCode.GUIDANCE]


@pytest.mark.django_db
def test_availability_requires_a_token(office):
    response = APIClient().get(availability_url(office.code))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_availability_lists_the_free_slots(student_client, office, employee, day):
    response = student_client.get(availability_url(office.code), {"date": day})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["office"] == OfficeCode.GUIDANCE
    assert body["date"] == day.isoformat()
    assert len(body["slots"]) == 16
    assert parse_datetime(body["slots"][0]) == slot_at(day, 9)


@pytest.mark.django_db
def test_availability_excludes_a_slot_nobody_is_free_for(
    student_client, office, employee, student, day
):
    student_client.post(
        "/api/appointments/",
        {
            "office": office.code,
            "slot": slot_at(day, 9).isoformat(),
            "question_text": "Una domanda.",
            "question_lang": "it",
        },
        format="json",
    )

    response = student_client.get(availability_url(office.code), {"date": day})

    assert parse_datetime(response.json()["slots"][0]) == slot_at(day, 9, 30)


@pytest.mark.django_db
def test_availability_is_empty_for_an_office_without_employees(
    student_client, office, day
):
    response = student_client.get(availability_url(office.code), {"date": day})

    assert response.json()["slots"] == []


@pytest.mark.django_db
def test_availability_requires_a_date(student_client, office, employee):
    response = student_client.get(availability_url(office.code))

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_availability_rejects_a_malformed_date(student_client, office, employee):
    response = student_client.get(availability_url(office.code), {"date": "28-09-2026"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_availability_of_an_unknown_office_is_not_found(student_client, day):
    response = student_client.get(availability_url("CANTEEN"), {"date": day})

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_availability_of_an_inactive_office_is_not_found(
    student_client, inactive_office, day
):
    make_employee(inactive_office, "paolo.gialli@unibo.it")

    response = student_client.get(availability_url(inactive_office.code), {"date": day})

    assert response.status_code == status.HTTP_404_NOT_FOUND
