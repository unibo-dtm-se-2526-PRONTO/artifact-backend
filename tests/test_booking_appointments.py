"""Tests for the appointment endpoints.

The booking rules themselves live in `test_booking_services.py`; what is
checked here is the HTTP contract on top of them — who may call what, what
comes back, and which errors reach the client.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from booking.models import Appointment
from pronto.enums import AppointmentStatus, OfficeCode, Role
from tests.conftest import authenticate, make_employee, make_user, slot_at

APPOINTMENTS_URL = "/api/appointments/"


def cancel_url(appointment_id):
    return f"{APPOINTMENTS_URL}{appointment_id}/cancel/"


def booking_payload(office, slot):
    return {
        "office": office.code,
        "slot": slot.isoformat(),
        "question_text": "Vorrei informazioni sul piano di studi.",
        "question_lang": "it",
    }


@pytest.fixture
def appointment(student_client, office, employee, day):
    response = student_client.post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
    )
    return Appointment.objects.get(pk=response.json()["id"])


# --- booking -----------------------------------------------------------------


@pytest.mark.django_db
def test_a_student_can_book_an_appointment(
    student_client, office, employee, student, day
):
    response = student_client.post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["office"] == OfficeCode.GUIDANCE
    assert body["student"] == student.email
    assert body["employee"] == employee.user.email
    assert body["status"] == AppointmentStatus.BOOKED


@pytest.mark.django_db
def test_booking_requires_a_token(office, employee, day):
    response = APIClient().post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not Appointment.objects.exists()


@pytest.mark.django_db
def test_an_employee_cannot_book_an_appointment(employee_client, office, employee, day):
    response = employee_client.post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Appointment.objects.exists()


@pytest.mark.django_db
def test_the_client_cannot_choose_the_employee(student_client, office, employee, day):
    colleague = make_employee(office, "luca.verdi@unibo.it")
    payload = booking_payload(office, slot_at(day, 9)) | {"employee": colleague.id}

    response = student_client.post(APPOINTMENTS_URL, payload, format="json")

    # Assigned by the service, from the office's own staff, not by the caller.
    assert response.json()["employee"] == employee.user.email


@pytest.mark.django_db
def test_booking_a_slot_nobody_is_free_for_is_rejected(
    student_client, office, employee, day
):
    student_client.post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
    )
    other_client = authenticate(make_user("lucia.neri@studio.unibo.it", "STUDENT"))

    response = other_client.post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Appointment.objects.count() == 1


@pytest.mark.django_db
def test_booking_a_slot_outside_the_opening_hours_is_rejected(
    student_client, office, employee, day
):
    response = student_client.post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 8)), format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_booking_an_unknown_office_is_rejected(student_client, office, employee, day):
    payload = booking_payload(office, slot_at(day, 9)) | {"office": "CANTEEN"}

    response = student_client.post(APPOINTMENTS_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_booking_without_a_question_is_rejected(student_client, office, employee, day):
    payload = booking_payload(office, slot_at(day, 9))
    del payload["question_text"]

    response = student_client.post(APPOINTMENTS_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


# --- listing -----------------------------------------------------------------


@pytest.mark.django_db
def test_listing_requires_a_token():
    response = APIClient().get(APPOINTMENTS_URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_a_student_sees_only_their_own_appointments(
    student_client, office, employee, appointment
):
    other_client = authenticate(make_user("lucia.neri@studio.unibo.it", "STUDENT"))

    assert [item["id"] for item in student_client.get(APPOINTMENTS_URL).json()] == [
        appointment.id
    ]
    assert other_client.get(APPOINTMENTS_URL).json() == []


@pytest.mark.django_db
def test_an_employee_sees_the_appointments_assigned_to_them(
    employee_client, office, employee, appointment
):
    response = employee_client.get(APPOINTMENTS_URL)

    assert [item["id"] for item in response.json()] == [appointment.id]


@pytest.mark.django_db
def test_an_admin_sees_every_appointment(appointment):
    admin_client = authenticate(make_user("rettorato@unibo.it", Role.ADMIN))

    response = admin_client.get(APPOINTMENTS_URL)

    assert [item["id"] for item in response.json()] == [appointment.id]


@pytest.mark.django_db
def test_an_employee_does_not_see_a_colleagues_appointments(
    office, employee, appointment
):
    colleague = make_employee(office, "luca.verdi@unibo.it")

    response = authenticate(colleague.user).get(APPOINTMENTS_URL)

    assert response.json() == []


# --- cancelling --------------------------------------------------------------


@pytest.mark.django_db
def test_a_student_can_cancel_their_own_appointment(student_client, appointment):
    response = student_client.post(cancel_url(appointment.id))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.CANCELLED


@pytest.mark.django_db
def test_cancelling_someone_elses_appointment_is_not_found(student_client, appointment):
    other_client = authenticate(make_user("lucia.neri@studio.unibo.it", "STUDENT"))

    response = other_client.post(cancel_url(appointment.id))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.BOOKED


@pytest.mark.django_db
def test_cancelling_twice_is_rejected(student_client, appointment):
    student_client.post(cancel_url(appointment.id))

    response = student_client.post(cancel_url(appointment.id))

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_the_employee_can_cancel_an_appointment_assigned_to_them(
    employee_client, appointment
):
    response = employee_client.post(cancel_url(appointment.id))

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_cancelling_frees_the_slot_for_another_student(
    student_client, office, employee, appointment, day
):
    student_client.post(cancel_url(appointment.id))
    other_client = authenticate(make_user("lucia.neri@studio.unibo.it", "STUDENT"))

    response = other_client.post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
