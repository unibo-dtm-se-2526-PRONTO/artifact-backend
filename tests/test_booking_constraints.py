"""The database's own guarantee behind FR9.

`tests/test_booking_services.py` checks that the service reacts well when it
loses a race. These tests check the thing it relies on: the partial unique
index that makes losing the race possible at all. They write through the ORM
directly, bypassing the service, because that is the point — the invariant has
to hold even for a caller that never asks the service's permission.
"""

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
    """The constraint is conditional, and this is the reason it has to be.

    An unconditional unique index would keep the slot locked forever by a
    booking nobody is going to attend.
    """
    slot = slot_at(day, 9)
    appointment(student, office, employee, slot, status=AppointmentStatus.CANCELLED)

    second = appointment(student, office, employee, slot)

    assert second.pk is not None
    assert Appointment.objects.filter(slot=slot).count() == 2
