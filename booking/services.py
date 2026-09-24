"""The booking rules: when an office is free, and who takes a booking.

This module exists because of an invariant the schema cannot express (see
``booking.models.Appointment``): an appointment's employee must work for the
appointment's office. Here the employee is *chosen from* ``office.employees``,
so the invariant holds by construction, and every booking goes through this
one door.

Availability is derived, never stored (FR4). An office's day is laid on a grid
that starts at midnight and steps by ``office.slot_duration_minutes``; a slot
on that grid is open when an employee has a shift covering the whole of it,
and bookable while one of those employees is free. Shifts go through this
module too, so the grid and the booked appointments are checked on the way in
and on the way out.
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
    """A shift that cannot be withdrawn: booked appointments still fall in it.

    Carries them, so the employee is told which ones to cancel first.
    """

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
    """Who is on duty in each slot of `office`'s `day`: ``{slot: {employee_id}}``.

    Only slots some shift covers whole appear, so the keys are exactly the
    office's opening grid for that day. A shift that no longer sits on the grid
    — the office's slot length changed after it was declared — offers the
    slots it still covers and nothing past its end.
    """
    step = office.slot_duration_minutes
    roster = {}
    shifts = Shift.objects.filter(
        employee__office=office, weekday=day.weekday()
    ).values_list("employee_id", "start_time", "end_time")

    for employee_id, start_time, end_time in shifts:
        # The first grid point at or after the start of the shift.
        start = -(-_minutes(start_time) // step) * step
        for minute in range(start, _minutes(end_time) - step + 1, step):
            # Built from the wall clock, not by adding minutes to midnight, so
            # a DST change on the day does not shift every slot by an hour.
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
    """The slots of `day` a student can still book at `office`.

    A slot survives while at least one employee on duty in it is free: the
    office is as available as its least busy member of staff.
    """
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

    `suggested_faq` is the FAQ the student was shown and did not find helpful,
    if any; it is passed on to the employee. Both are e-mailed once the
    booking commits.

    Raises `BookingError`, never returns a half-booked appointment.
    """
    if not office.is_active:
        raise BookingError("This office is not accepting bookings.")
    if slot <= timezone.now():
        raise BookingError("This slot is in the past.")

    on_duty = _on_duty(office, slot).count()
    if on_duty == 0:
        raise BookingError("This office is closed at that time.")

    # seq2: every lost race means one more employee now busy at `slot`, so
    # there are never more attempts than people on duty.
    lost_a_race = False
    for _attempt in range(on_duty):
        employee = _free_employee(office, slot)
        if employee is None:
            break
        try:
            # Atomic so the IntegrityError below leaves no broken transaction
            # behind for the next attempt, or for the caller's own queries.
            with transaction.atomic():
                appointment = Appointment.objects.create(
                    student=student,
                    office=office,
                    employee=employee,
                    slot=slot,
                    question_text=question_text,
                    question_lang=question_lang,
                    suggested_faq=suggested_faq,
                )
                # Inside the savepoint: a lost race rolls the e-mails back
                # with the row, so nobody hears about a booking that failed.
                notifications.appointment_booked(appointment)
                return appointment
        except IntegrityError:
            # Another request booked the same employee between the query in
            # `_free_employee` and this insert. The partial unique index
            # settled it; a colleague on duty may still be free.
            lost_a_race = True

    if lost_a_race:
        raise BookingError("This slot has just been taken.")
    raise BookingError("No employee is available at this slot.")


def declare_shift(*, employee, weekday, start_time, end_time):
    """Record that `employee` is on duty every `weekday` from start to end.

    Refused unless the shift sits on the office's slot grid — a 9:15 start at a
    30-minute office would lose a quarter of an hour without anyone noticing —
    and overlaps none of the employee's other shifts.
    """
    step = employee.office.slot_duration_minutes
    if start_time >= end_time:
        raise BookingError("A shift has to end after it starts.")
    if not (_is_on_grid(start_time, step) and _is_on_grid(end_time, step)):
        raise BookingError(
            f"A shift has to start and end on the office's {step}-minute slots."
        )

    with transaction.atomic():
        # Locks the employee, so two shifts declared at once cannot both pass
        # the overlap check. A no-op on SQLite, which serialises writes anyway.
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
    """Delete `shift`, unless booked appointments still fall inside it.

    Only the employee's own future appointments count: a colleague's are
    covered by the colleague's shifts, and a past one no longer needs anyone
    on duty. Refusing, rather than cancelling them, keeps the choice with a
    person: the employee cancels them first, and each student is told.
    """
    with transaction.atomic():
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
    """Cancel a booked appointment, freeing its slot for someone else.

    `by` is the user cancelling: whoever else is involved is e-mailed once the
    cancellation commits (FR15).
    """
    if appointment.status != AppointmentStatus.BOOKED:
        raise BookingError("Only a booked appointment can be cancelled.")
    if appointment.slot <= timezone.now():
        raise BookingError(
            "An appointment that has already started cannot be cancelled."
        )

    with transaction.atomic():
        appointment.status = AppointmentStatus.CANCELLED
        # updated_at is auto_now: left out of update_fields it would not be touched.
        appointment.save(update_fields=["status", "updated_at"])
        notifications.appointment_cancelled(appointment, by=by)
    return appointment


def complete_appointment(appointment):
    """Record that a booked meeting has taken place.

    Refused before the slot begins: "completed" means the employee answered
    the student, and nobody can answer a question at a meeting that has not
    started. It is the mirror of the rule in `cancel_appointment`, which
    refuses to call off a meeting already under way.

    Completing does not free the slot for anyone else — the constraint is
    conditional on BOOKED, so the row stops reserving the employee, but the
    slot is in the past by then and `available_slots` no longer offers it.
    """
    if appointment.status != AppointmentStatus.BOOKED:
        raise BookingError("Only a booked appointment can be completed.")
    if appointment.slot > timezone.now():
        raise BookingError("This appointment has not started yet.")

    appointment.status = AppointmentStatus.COMPLETED
    # updated_at is auto_now: left out of update_fields it would not be touched.
    appointment.save(update_fields=["status", "updated_at"])
    return appointment


def _free_employee(office, slot):
    """The least busy employee on duty at `slot` with nothing booked there.

    Load is counted over every appointment still BOOKED, not just this day's:
    what the helpdesk shares out is the work waiting to be done, and an
    appointment cancelled or completed is no longer work.

    Ties break on primary key, so the choice stays deterministic — the tests
    can name who gets a booking, and two identical situations never resolve
    differently. Under simultaneous requests the balance is best-effort, as
    the counts are read before the insert; what is guaranteed is only that
    nobody is double-booked, which is the database's job (see `Meta.constraints`
    on `Appointment`).
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
