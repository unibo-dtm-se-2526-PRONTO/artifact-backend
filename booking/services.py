"""Booking rules: when an office is free and who takes a booking.

Every booking goes through here, so the employee always works for the office.
Availability is computed from the shifts, never stored (FR4): a day is a grid
of `office.slot_duration_minutes` slots starting at midnight.
"""

from datetime import datetime, time

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from pronto.enums import AppointmentStatus

from . import notifications
from .models import Appointment, EmployeeProfile, Shift

MINUTES_IN_A_DAY = 24 * 60


class BookingError(Exception):
    """A booking the rules refuse. The views turn it into a 400."""


class ShiftInUseError(BookingError):
    """A shift that still covers booked appointments, listed in `appointments`."""

    def __init__(self, appointments):
        super().__init__(
            "This shift still covers booked appointments: cancel them first."
        )
        self.appointments = appointments


def _minutes(moment):
    """Minutes since midnight of a `time`."""
    return moment.hour * 60 + moment.minute


def _is_on_grid(moment, step):
    return (
        moment.second == 0 and moment.microsecond == 0 and _minutes(moment) % step == 0
    )


def _roster(office, day):
    """Who is on duty in each slot of `office`'s `day`: ``{slot: {employee_id}}``."""
    step = office.slot_duration_minutes
    roster = {}
    shifts = Shift.objects.filter(
        employee__office=office, weekday=day.weekday()
    ).values_list("employee_id", "start_time", "end_time")

    for employee_id, start_time, end_time in shifts:
        # The first grid point at or after the start of the shift.
        start = -(-_minutes(start_time) // step) * step
        for minute in range(start, _minutes(end_time) - step + 1, step):
            # From the wall clock, so a DST change does not shift the slots.
            slot = timezone.make_aware(
                datetime.combine(day, time(minute // 60, minute % 60))
            )
            roster.setdefault(slot, set()).add(employee_id)
    return roster


def _on_duty(office, slot):
    """The employees of `office` whose shift covers the whole of `slot`."""
    local = timezone.localtime(slot)
    step = office.slot_duration_minutes
    start = _minutes(local.time())
    end = start + step
    if not _is_on_grid(local.time(), step) or end >= MINUTES_IN_A_DAY:
        return office.employees.none()

    covering = Shift.objects.filter(
        weekday=local.weekday(),
        start_time__lte=local.time(),
        end_time__gte=time(end // 60, end % 60),
    )
    return office.employees.filter(pk__in=covering.values("employee_id"))


def available_slots(office, day):
    """The future slots of `day` where at least one employee on duty is free."""
    if not office.is_active:
        return []

    roster = _roster(office, day)
    busy = {}
    for slot, employee_id in Appointment.objects.filter(
        office=office, status=AppointmentStatus.BOOKED, slot__in=list(roster)
    ).values_list("slot", "employee_id"):
        busy.setdefault(slot, set()).add(employee_id)

    now = timezone.now()
    return sorted(
        slot
        for slot, on_duty in roster.items()
        if slot > now and on_duty - busy.get(slot, set())
    )


def book_appointment(
    *, student, office, slot, question_text, question_lang, suggested_faq=None
):
    """Book `slot` at `office` for `student`, assigning a free employee.

    `suggested_faq` is the FAQ the student did not find helpful, if any.
    Raises `BookingError`.
    """
    if not office.is_active:
        raise BookingError("This office is not accepting bookings.")
    if slot <= timezone.now():
        raise BookingError("This slot is in the past.")

    on_duty = _on_duty(office, slot).count()
    if on_duty == 0:
        raise BookingError("This office is closed at that time.")

    # seq2: each lost race makes one more employee busy, so at most one try each.
    lost_a_race = False
    for _attempt in range(on_duty):
        employee = _free_employee(office, slot)
        if employee is None:
            break
        try:
            with transaction.atomic():
                # Same lock as `withdraw_shift`, then the shift is checked again.
                EmployeeProfile.objects.select_for_update().get(pk=employee.pk)
                if not _on_duty(office, slot).filter(pk=employee.pk).exists():
                    continue
                appointment = Appointment.objects.create(
                    student=student,
                    office=office,
                    employee=employee,
                    slot=slot,
                    question_text=question_text,
                    question_lang=question_lang,
                    suggested_faq=suggested_faq,
                )
                # Inside the savepoint, so a lost race sends no e-mail.
                notifications.appointment_booked(appointment)
                return appointment
        except IntegrityError:
            # The unique index refused a double booking; try a colleague.
            lost_a_race = True

    if lost_a_race:
        raise BookingError("This slot has just been taken.")
    raise BookingError("No employee is available at this slot.")


def declare_shift(*, employee, weekday, start_time, end_time):
    """Record that `employee` is on duty every `weekday` from start to end.

    The shift must sit on the office's slot grid and overlap no other shift.
    """
    step = employee.office.slot_duration_minutes
    if start_time >= end_time:
        raise BookingError("A shift has to end after it starts.")
    if not (_is_on_grid(start_time, step) and _is_on_grid(end_time, step)):
        raise BookingError(
            f"A shift has to start and end on the office's {step}-minute slots."
        )

    with transaction.atomic():
        # So two shifts declared at once cannot both pass the overlap check.
        EmployeeProfile.objects.select_for_update().get(pk=employee.pk)
        overlapping = employee.shifts.filter(
            weekday=weekday, start_time__lt=end_time, end_time__gt=start_time
        )
        if overlapping.exists():
            raise BookingError("This shift overlaps another of your shifts.")
        return Shift.objects.create(
            employee=employee,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
        )


def withdraw_shift(shift):
    """Delete `shift`, unless the employee's future bookings still fall inside it.

    Locks the employee like `book_appointment`, so no booking slips in meanwhile.
    """
    with transaction.atomic():
        EmployeeProfile.objects.select_for_update().get(pk=shift.employee_id)
        held = list(
            Appointment.objects.filter(
                employee=shift.employee,
                status=AppointmentStatus.BOOKED,
                slot__gt=timezone.now(),
                # iso_week_day runs 1-7 from Monday; weekday runs 0-6.
                slot__iso_week_day=shift.weekday + 1,
                slot__time__gte=shift.start_time,
                slot__time__lt=shift.end_time,
            ).order_by("slot")
        )
        if held:
            raise ShiftInUseError(held)
        shift.delete()


def cancel_appointment(appointment, *, by):
    """Cancel a booked appointment; the other party is e-mailed (FR15).

    `by` is the user cancelling. The row is locked so a double click cancels once.
    """
    with transaction.atomic():
        appointment.status = (
            Appointment.objects.select_for_update()
            .values_list("status", flat=True)
            .get(pk=appointment.pk)
        )
        if appointment.status != AppointmentStatus.BOOKED:
            raise BookingError("Only a booked appointment can be cancelled.")
        if appointment.slot <= timezone.now():
            raise BookingError(
                "An appointment that has already started cannot be cancelled."
            )

        appointment.status = AppointmentStatus.CANCELLED
        # updated_at is auto_now: left out of update_fields it would not be touched.
        appointment.save(update_fields=["status", "updated_at"])
        notifications.appointment_cancelled(appointment, by=by)
    return appointment


def complete_appointment(appointment):
    """Record that a booked meeting has taken place, once its slot has started."""
    if appointment.status != AppointmentStatus.BOOKED:
        raise BookingError("Only a booked appointment can be completed.")
    if appointment.slot > timezone.now():
        raise BookingError("This appointment has not started yet.")

    appointment.status = AppointmentStatus.COMPLETED
    # updated_at is auto_now: left out of update_fields it would not be touched.
    appointment.save(update_fields=["status", "updated_at"])
    return appointment


def _free_employee(office, slot):
    """The free employee on duty at `slot` with the fewest BOOKED appointments.

    Ties break on primary key. Under concurrent requests the balance is
    best effort; double bookings are prevented by `Appointment.Meta.constraints`.
    """
    busy = Appointment.objects.filter(
        slot=slot, status=AppointmentStatus.BOOKED, employee__office=office
    ).values_list("employee_id", flat=True)
    return (
        _on_duty(office, slot)
        .exclude(pk__in=busy)
        .annotate(
            load=Count(
                "appointments",
                filter=Q(appointments__status=AppointmentStatus.BOOKED),
            )
        )
        .order_by("load", "pk")
        .first()
    )
