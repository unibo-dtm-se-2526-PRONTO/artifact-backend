"""The booking rules: when an office is free, and who takes a booking.

This module exists because of an invariant the schema cannot express (see
``booking.models.Appointment``): an appointment's employee must work for the
appointment's office. Here the employee is *chosen from* ``office.employees``,
so the invariant holds by construction, and every booking goes through this
one door.

Opening hours are settings rather than a model. The helpdesk keeps the same
hours at every office, and only the length of a slot varies, which `Office`
already stores. If offices ever need their own calendars, this is the seam
where a schedule model would replace the settings.
"""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from pronto.enums import AppointmentStatus

from .models import Appointment


class BookingError(Exception):
    """A booking the rules refuse. The views turn it into a 400."""


def opening_grid(office, day):
    """Every slot the office's timetable defines for `day`, free or not.

    Availability is not considered here: this is the shape of the day, which
    both `available_slots` and `book_appointment` measure a slot against.
    """
    if day.weekday() not in settings.BOOKING_WORKING_DAYS:
        return []

    slot = timezone.make_aware(
        datetime.combine(day, time(settings.BOOKING_OPENING_HOUR))
    )
    closing = timezone.make_aware(
        datetime.combine(day, time(settings.BOOKING_CLOSING_HOUR))
    )
    step = timedelta(minutes=office.slot_duration_minutes)

    slots = []
    # A slot has to *end* by closing time, so the last one starts a step early.
    while slot + step <= closing:
        slots.append(slot)
        slot += step
    return slots


def available_slots(office, day):
    """The slots of `day` a student can still book at `office`.

    A slot survives while at least one employee is free: the office is as
    available as its least busy member of staff.
    """
    if not office.is_active:
        return []

    staff_count = office.employees.count()
    if staff_count == 0:
        return []

    grid = opening_grid(office, day)
    taken = {
        row["slot"]: row["count"]
        for row in Appointment.objects.filter(
            office=office, status=AppointmentStatus.BOOKED, slot__in=grid
        )
        .values("slot")
        .annotate(count=Count("id"))
    }

    now = timezone.now()
    return [slot for slot in grid if slot > now and taken.get(slot, 0) < staff_count]


def book_appointment(*, student, office, slot, question_text, question_lang):
    """Book `slot` at `office` for `student`, assigning a free employee.

    Raises `BookingError`, never returns a half-booked appointment.
    """
    if not office.is_active:
        raise BookingError("This office is not accepting bookings.")
    if slot <= timezone.now():
        raise BookingError("This slot is in the past.")
    if slot not in opening_grid(office, timezone.localtime(slot).date()):
        raise BookingError("This office is closed at that time.")

    employee = _free_employee(office, slot)
    if employee is None:
        raise BookingError("No employee is available at this slot.")

    try:
        # Atomic so the IntegrityError below leaves no broken transaction
        # behind for the caller's own queries.
        with transaction.atomic():
            return Appointment.objects.create(
                student=student,
                office=office,
                employee=employee,
                slot=slot,
                question_text=question_text,
                question_lang=question_lang,
            )
    except IntegrityError as error:
        # Two students picked the same free employee between the query above
        # and this insert. The partial unique index settles it; the loser is
        # told to pick again rather than silently reassigned.
        raise BookingError("This slot has just been taken.") from error


def cancel_appointment(appointment):
    """Cancel a booked appointment, freeing its slot for someone else."""
    if appointment.status != AppointmentStatus.BOOKED:
        raise BookingError("Only a booked appointment can be cancelled.")
    if appointment.slot <= timezone.now():
        raise BookingError(
            "An appointment that has already started cannot be cancelled."
        )

    appointment.status = AppointmentStatus.CANCELLED
    # updated_at is auto_now: left out of update_fields it would not be touched.
    appointment.save(update_fields=["status", "updated_at"])
    return appointment


def _free_employee(office, slot):
    """An employee of `office` with nothing booked at `slot`, or None.

    Ordered by primary key rather than at random: a deterministic choice keeps
    the tests honest, and spreading the load is not this app's problem yet.
    """
    busy = Appointment.objects.filter(
        slot=slot, status=AppointmentStatus.BOOKED, employee__office=office
    ).values_list("employee_id", flat=True)
    return office.employees.exclude(pk__in=busy).order_by("pk").first()
