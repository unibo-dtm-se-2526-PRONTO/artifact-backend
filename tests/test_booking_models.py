"""Tests for the booking models: offices, employee profiles and appointments.

`office`, `student` and `employee` come from `tests/conftest.py`. The
constraint on (employee, slot) is tested in `tests/test_booking_constraints.py`.
"""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils import timezone

from booking.models import Appointment, EmployeeProfile, Office
from pronto.enums import AppointmentStatus, OfficeCode
from tests.conftest import make_employee


@pytest.fixture
def slot():
    return timezone.now() + timedelta(days=1)


def book(student, employee, slot, **overrides):
    """Book an appointment with the given employee, defaults filled in."""
    fields = {
        "student": student,
        "office": employee.office,
        "employee": employee,
        "slot": slot,
        "question_text": "Come richiedo il riconoscimento dei crediti?",
        "question_lang": "it",
    }
    return Appointment.objects.create(**{**fields, **overrides})


# --- Office ---------------------------------------------------------------


def test_office_codes_come_from_the_shared_enum():
    assert Office._meta.get_field("code").choices == OfficeCode.choices


@pytest.mark.django_db
def test_a_new_office_is_active_and_books_half_hour_slots():
    # Created here rather than taken from conftest: the shared fixture sets
    # slot_duration_minutes explicitly, which would hide the default.
    office = Office.objects.create(
        code=OfficeCode.GUIDANCE,
        name_it="Orientamento",
        name_en="Guidance",
        contact_email="orientamento@unibo.it",
    )

    assert office.is_active
    assert office.slot_duration_minutes == 30


@pytest.mark.django_db
def test_an_office_is_displayed_by_its_italian_name(office):
    assert str(office) == "Orientamento"


@pytest.mark.django_db
def test_two_offices_cannot_share_a_code(office):
    with pytest.raises(IntegrityError):
        Office.objects.create(
            code=OfficeCode.GUIDANCE,
            name_it="Orientamento (bis)",
            name_en="Guidance (bis)",
            contact_email="altro@unibo.it",
        )


# --- EmployeeProfile ------------------------------------------------------


@pytest.mark.django_db
def test_an_employee_is_reachable_from_their_office(employee, office):
    assert list(office.employees.all()) == [employee]


@pytest.mark.django_db
def test_an_employee_is_displayed_by_email_and_office(employee):
    assert str(employee) == "anna.bianchi@unibo.it (GUIDANCE)"


@pytest.mark.django_db
def test_an_employee_staffs_exactly_one_office(employee, office):
    other_office = Office.objects.create(
        code=OfficeCode.INTERNSHIPS,
        name_it="Tirocini",
        name_en="Internships",
        contact_email="tirocini@unibo.it",
    )

    with pytest.raises(IntegrityError):
        EmployeeProfile.objects.create(user=employee.user, office=other_office)


@pytest.mark.django_db
def test_deleting_an_employees_account_removes_their_profile(employee):
    employee.user.delete()

    assert not EmployeeProfile.objects.exists()


@pytest.mark.django_db
def test_an_office_with_staff_cannot_be_deleted(employee, office):
    # PROTECT: emptying an office has to be a deliberate act, never a side
    # effect of deleting the office row.
    with pytest.raises(ProtectedError):
        office.delete()


# --- Appointment ----------------------------------------------------------


@pytest.mark.django_db
def test_a_new_appointment_is_booked(student, employee, slot):
    appointment = book(student, employee, slot)

    assert appointment.status == AppointmentStatus.BOOKED


@pytest.mark.django_db
def test_an_appointment_records_the_language_the_student_asked_in(
    student, employee, slot
):
    appointment = book(student, employee, slot, question_lang="en")

    assert appointment.question_lang == "en"


@pytest.mark.django_db
def test_an_unknown_question_language_is_rejected_by_validation(
    student, employee, slot
):
    appointment = book(student, employee, slot)
    appointment.question_lang = "de"

    with pytest.raises(ValidationError):
        appointment.full_clean()


@pytest.mark.django_db
def test_an_appointment_is_reachable_from_the_student(student, employee, slot):
    appointment = book(student, employee, slot)

    assert list(student.appointments.all()) == [appointment]


@pytest.mark.django_db
def test_appointments_are_listed_with_the_most_recent_slot_first(
    student, employee, slot
):
    later = book(student, employee, slot + timedelta(days=1))
    earlier = book(student, employee, slot)

    assert list(Appointment.objects.all()) == [later, earlier]


@pytest.mark.django_db
def test_two_employees_can_be_booked_in_the_same_slot(student, employee, slot):
    colleague = make_employee(employee.office, email="luca.verdi@unibo.it")
    book(student, employee, slot)

    book(student, colleague, slot)

    assert Appointment.objects.count() == 2


@pytest.mark.django_db
def test_deleting_a_student_removes_their_appointments(student, employee, slot):
    book(student, employee, slot)

    student.delete()

    assert not Appointment.objects.exists()


@pytest.mark.django_db
def test_an_employee_with_appointments_cannot_be_deleted(student, employee, slot):
    book(student, employee, slot)

    with pytest.raises(ProtectedError):
        employee.delete()


@pytest.mark.django_db
def test_an_office_with_appointments_cannot_be_deleted(student, employee, office, slot):
    book(student, employee, slot)

    with pytest.raises(ProtectedError):
        office.delete()


@pytest.mark.django_db
def test_an_appointment_is_displayed_by_slot_student_and_office(student, employee):
    when = timezone.make_aware(timezone.datetime(2026, 10, 1, 9, 30))

    appointment = book(student, employee, when)

    assert str(appointment) == (
        "2026-10-01 09:30 — mario.rossi@studio.unibo.it @ GUIDANCE"
    )
