"""The partial unique index behind FR9, tested through the ORM directly."""

import pytest
from django.db import IntegrityError, transaction

from booking.models import Appointment
from pronto.enums import AppointmentStatus
from tests.conftest import slot_at


def appointment(student, office, employee, slot, status=AppointmentStatus.BOOKED):
    return Appointment.objects.create(
        student=student,
        office=office,
        employee=employee,
        slot=slot,
        status=status,
        question_text="Vorrei informazioni sul piano di studi.",
        question_lang="it",
    )


@pytest.mark.django_db
def test_an_employee_cannot_hold_two_booked_appointments_on_one_slot(
    office, employee, student, day
):
    slot = slot_at(day, 9)
    appointment(student, office, employee, slot)

    with pytest.raises(IntegrityError), transaction.atomic():
        appointment(student, office, employee, slot)


@pytest.mark.django_db
def test_a_cancelled_appointment_does_not_block_the_slot(
    office, employee, student, day
):
    """Conditional, or a cancelled booking would block the slot forever."""
    slot = slot_at(day, 9)
    appointment(student, office, employee, slot, status=AppointmentStatus.CANCELLED)

    second = appointment(student, office, employee, slot)

    assert second.pk is not None
    assert Appointment.objects.filter(slot=slot).count() == 2
