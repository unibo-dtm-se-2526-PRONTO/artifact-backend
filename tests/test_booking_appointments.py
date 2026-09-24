"""Tests for the appointment endpoints.

The booking rules themselves live in `test_booking_services.py`; what is
checked here is the HTTP contract on top of them — who may call what, what
comes back, and which errors reach the client.
"""

from datetime import timedelta

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from booking.models import Appointment
from faq.models import Faq
from pronto.enums import AppointmentStatus, OfficeCode, Role
from tests.conftest import authenticate, make_employee, make_user, slot_at

APPOINTMENTS_URL = "/api/appointments/"


def cancel_url(appointment_id):
    return f"{APPOINTMENTS_URL}{appointment_id}/cancel/"


def complete_url(appointment_id):
    return f"{APPOINTMENTS_URL}{appointment_id}/complete/"


def move_to_the_past(appointment):
    """Rewind a booked appointment so it can be completed.

    Updated through a queryset rather than `save()`, so nothing recomputes
    `updated_at` behind the test's back: only the slot moves.
    """
    Appointment.objects.filter(pk=appointment.pk).update(
        slot=appointment.slot - timedelta(days=7)
    )
    appointment.refresh_from_db()
    return appointment


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


# --- completing --------------------------------------------------------------


@pytest.mark.django_db
def test_the_assigned_employee_can_complete_an_appointment(
    employee_client, appointment
):
    move_to_the_past(appointment)

    response = employee_client.post(complete_url(appointment.id))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.COMPLETED


@pytest.mark.django_db
def test_a_student_cannot_complete_their_own_appointment(student_client, appointment):
    """The student is the one asking the question, not the one answering it."""
    move_to_the_past(appointment)

    response = student_client.post(complete_url(appointment.id))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.BOOKED


@pytest.mark.django_db
def test_completing_a_colleagues_appointment_is_not_found(office, appointment):
    """404 rather than 403, as everywhere else: it is not their appointment."""
    colleague = make_employee(office, "luca.verdi@unibo.it")
    move_to_the_past(appointment)

    response = authenticate(colleague.user).post(complete_url(appointment.id))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.BOOKED


@pytest.mark.django_db
def test_completing_an_appointment_that_has_not_started_is_rejected(
    employee_client, appointment
):
    response = employee_client.post(complete_url(appointment.id))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.BOOKED


@pytest.mark.django_db
def test_a_completed_appointment_still_belongs_to_the_student(
    student_client, employee_client, appointment
):
    """Completing is not deleting: the student keeps the record of the meeting."""
    move_to_the_past(appointment)
    employee_client.post(complete_url(appointment.id))

    response = student_client.get(APPOINTMENTS_URL)

    assert [row["status"] for row in response.json()] == [AppointmentStatus.COMPLETED]


# --- the FAQ that did not help -----------------------------------------------


@pytest.fixture
def faq(db):
    return Faq.objects.create(
        office_code=OfficeCode.GUIDANCE,
        question_it="Come si modifica il piano di studi?",
        question_en="How do I change my study plan?",
        answer_it="Da Studenti Online, entro ottobre.",
        answer_en="On Studenti Online, by October.",
    )


@pytest.mark.django_db
def test_a_booking_can_name_the_faq_the_student_was_shown(
    student_client, office, employee, day, faq
):
    payload = booking_payload(office, slot_at(day, 9)) | {"faq_id": faq.id}

    response = student_client.post(APPOINTMENTS_URL, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["faq_id"] == faq.id
    assert Appointment.objects.get().suggested_faq == faq


@pytest.mark.django_db
def test_the_faq_is_optional(student_client, office, employee, day):
    response = student_client.post(
        APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["faq_id"] is None


@pytest.mark.django_db
def test_an_unknown_faq_is_a_field_error(student_client, office, employee, day):
    payload = booking_payload(office, slot_at(day, 9)) | {"faq_id": 999}

    response = student_client.post(APPOINTMENTS_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "faq_id" in response.json()
    assert not Appointment.objects.exists()


@pytest.mark.django_db
def test_an_unpublished_faq_is_a_field_error(
    student_client, office, employee, day, faq
):
    """A FAQ the student could not have been shown cannot be the one that
    failed them."""
    faq.is_active = False
    faq.save()
    payload = booking_payload(office, slot_at(day, 9)) | {"faq_id": faq.id}

    response = student_client.post(APPOINTMENTS_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "faq_id" in response.json()


# --- notifications through the API ------------------------------------------


@pytest.mark.django_db
def test_booking_through_the_api_notifies_both_sides(
    student_client,
    office,
    employee,
    student,
    day,
    mailoutbox,
    django_capture_on_commit_callbacks,
):
    with django_capture_on_commit_callbacks(execute=True):
        student_client.post(
            APPOINTMENTS_URL, booking_payload(office, slot_at(day, 9)), format="json"
        )

    assert sorted(message.to[0] for message in mailoutbox) == sorted(
        [student.email, employee.user.email]
    )


@pytest.mark.django_db
def test_the_api_tells_the_service_who_cancelled(
    employee_client,
    appointment,
    student,
    mailoutbox,
    django_capture_on_commit_callbacks,
):
    """The view passes the caller on, so the e-mail goes to the other side."""
    with django_capture_on_commit_callbacks(execute=True):
        employee_client.post(cancel_url(appointment.id))

    assert [message.to for message in mailoutbox] == [[student.email]]
