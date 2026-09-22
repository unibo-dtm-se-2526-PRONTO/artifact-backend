"""Tests for the booking rules in `booking.services`.

These are the domain tests: no HTTP, no serializers. They pin down when a slot
is free, who a booking is assigned to, and which bookings are refused.

Dates are built relative to today, never hard-coded, so the suite does not rot:
the shared `day` fixture always lands on a weekday in the future, which is what
every "can be booked" case needs.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model

from booking.models import Appointment
from booking.services import (
    BookingError,
    available_slots,
    book_appointment,
    cancel_appointment,
)
from pronto.enums import AppointmentStatus
from tests.conftest import make_employee, make_user, slot_at

User = get_user_model()


def book(student, office, slot):
    return book_appointment(
        student=student,
        office=office,
        slot=slot,
        question_text="Vorrei informazioni sul piano di studi.",
        question_lang="it",
    )


# --- available_slots ---------------------------------------------------------


@pytest.mark.django_db
def test_available_slots_spans_the_opening_hours(office, employee, day):
    slots = available_slots(office, day)

    assert slots[0] == slot_at(day, 9)
    # The last slot starts half an hour before closing, so it ends at 17:00.
    assert slots[-1] == slot_at(day, 16, 30)
    assert len(slots) == 16


@pytest.mark.django_db
def test_available_slots_follows_the_office_slot_duration(office, employee, day):
    office.slot_duration_minutes = 60
    office.save()

    slots = available_slots(office, day)

    assert slots[1] - slots[0] == timedelta(hours=1)
    assert len(slots) == 8


@pytest.mark.django_db
def test_available_slots_is_empty_at_the_weekend(office, employee, day):
    saturday = day + timedelta(days=5)

    assert available_slots(office, saturday) == []


@pytest.mark.django_db
def test_available_slots_is_empty_for_a_past_day(office, employee, day):
    assert available_slots(office, day - timedelta(days=7)) == []


@pytest.mark.django_db
def test_available_slots_is_empty_for_an_inactive_office(office, employee, day):
    office.is_active = False
    office.save()

    assert available_slots(office, day) == []


@pytest.mark.django_db
def test_available_slots_is_empty_for_an_office_without_employees(office, day):
    assert available_slots(office, day) == []


@pytest.mark.django_db
def test_a_slot_stays_available_while_one_employee_is_free(
    office, employee, student, day
):
    make_employee(office, "luca.verdi@unibo.it")
    slot = slot_at(day, 10)
    book(student, office, slot)

    assert slot in available_slots(office, day)


@pytest.mark.django_db
def test_a_slot_disappears_when_every_employee_is_booked(office, employee, day):
    slot = slot_at(day, 10)
    for email in ("a@studio.unibo.it", "b@studio.unibo.it"):
        student = make_user(email, User.Role.STUDENT)
        try:
            book(student, office, slot)
        except BookingError:
            pass

    assert slot not in available_slots(office, day)


@pytest.mark.django_db
def test_a_cancelled_appointment_frees_the_slot(office, employee, student, day):
    slot = slot_at(day, 10)
    appointment = book(student, office, slot)
    assert slot not in available_slots(office, day)

    cancel_appointment(appointment)

    assert slot in available_slots(office, day)


# --- book_appointment --------------------------------------------------------


@pytest.mark.django_db
def test_book_appointment_assigns_an_employee_of_that_office(
    office, employee, student, day
):
    appointment = book(student, office, slot_at(day, 9))

    # The invariant the schema cannot express: see booking/models.py.
    assert appointment.employee == employee
    assert appointment.employee.office == appointment.office


@pytest.mark.django_db
def test_book_appointment_records_the_question_and_starts_as_booked(
    office, employee, student, day
):
    appointment = book(student, office, slot_at(day, 9))

    assert appointment.student == student
    assert appointment.status == AppointmentStatus.BOOKED
    assert appointment.question_text == "Vorrei informazioni sul piano di studi."
    assert appointment.question_lang == "it"


@pytest.mark.django_db
def test_two_bookings_at_the_same_slot_get_different_employees(
    office, employee, student, day
):
    colleague = make_employee(office, "luca.verdi@unibo.it")
    other_student = make_user("lucia.neri@studio.unibo.it", User.Role.STUDENT)
    slot = slot_at(day, 11)

    first = book(student, office, slot)
    second = book(other_student, office, slot)

    assert {first.employee, second.employee} == {employee, colleague}


@pytest.mark.django_db
def test_book_appointment_rejects_a_slot_in_the_past(office, employee, student, day):
    with pytest.raises(BookingError):
        book(student, office, slot_at(day - timedelta(days=7), 9))


@pytest.mark.django_db
def test_book_appointment_rejects_a_slot_before_opening(office, employee, student, day):
    with pytest.raises(BookingError):
        book(student, office, slot_at(day, 8))


@pytest.mark.django_db
def test_book_appointment_rejects_a_slot_after_closing(office, employee, student, day):
    with pytest.raises(BookingError):
        book(student, office, slot_at(day, 17))


@pytest.mark.django_db
def test_book_appointment_rejects_a_slot_off_the_grid(office, employee, student, day):
    with pytest.raises(BookingError):
        book(student, office, slot_at(day, 9, 15))


@pytest.mark.django_db
def test_book_appointment_rejects_a_weekend_slot(office, employee, student, day):
    with pytest.raises(BookingError):
        book(student, office, slot_at(day + timedelta(days=5), 9))


@pytest.mark.django_db
def test_book_appointment_rejects_an_inactive_office(office, employee, student, day):
    office.is_active = False
    office.save()

    with pytest.raises(BookingError):
        book(student, office, slot_at(day, 9))


@pytest.mark.django_db
def test_book_appointment_rejects_an_office_without_employees(office, student, day):
    with pytest.raises(BookingError):
        book(student, office, slot_at(day, 9))


@pytest.mark.django_db
def test_book_appointment_fails_when_every_employee_is_busy(
    office, employee, student, day
):
    slot = slot_at(day, 9)
    book(student, office, slot)
    other_student = make_user("lucia.neri@studio.unibo.it", User.Role.STUDENT)

    with pytest.raises(BookingError):
        book(other_student, office, slot)


# --- cancel_appointment ------------------------------------------------------


@pytest.mark.django_db
def test_cancel_appointment_marks_it_cancelled(office, employee, student, day):
    appointment = book(student, office, slot_at(day, 9))

    cancel_appointment(appointment)

    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.CANCELLED


@pytest.mark.django_db
def test_cancel_appointment_rejects_an_already_cancelled_one(
    office, employee, student, day
):
    appointment = book(student, office, slot_at(day, 9))
    cancel_appointment(appointment)

    with pytest.raises(BookingError):
        cancel_appointment(appointment)


@pytest.mark.django_db
def test_cancel_appointment_rejects_a_past_appointment(office, employee, student, day):
    # Created straight through the ORM: the service would refuse to book it.
    appointment = Appointment.objects.create(
        student=student,
        office=office,
        employee=employee,
        slot=slot_at(day - timedelta(days=7), 9),
        question_text="Domanda di ieri.",
        question_lang="it",
    )

    with pytest.raises(BookingError):
        cancel_appointment(appointment)
