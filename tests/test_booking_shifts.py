"""Tests for shifts: how they are declared, withdrawn, and turned into slots.

These are domain tests, like `test_booking_services.py`: no HTTP. They pin
down FR4 (availability is derived from shifts, not stored) and FR5 (a shift
can be added or removed afterwards, and the change shows up at once), plus the
two rules that keep that safe — shifts sit on the office's slot grid, and a
shift cannot be withdrawn from under a booked appointment.
"""

from datetime import time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from booking.models import Appointment, Shift
from booking.services import (
    BookingError,
    ShiftInUseError,
    available_slots,
    book_appointment,
    cancel_appointment,
    declare_shift,
    withdraw_shift,
)
from pronto.enums import AppointmentStatus
from tests.conftest import make_employee, make_user, slot_at

User = get_user_model()

MONDAY = 0


def book(student, office, slot):
    return book_appointment(
        student=student,
        office=office,
        slot=slot,
        question_text="Vorrei informazioni sul piano di studi.",
        question_lang="it",
    )


@pytest.fixture
def newcomer(office):
    """An employee of `office` who has not declared any shift yet."""
    return make_employee(office, "nuovo.arrivato@unibo.it", shifts=[])


# --- Shift model -------------------------------------------------------------


@pytest.mark.django_db
def test_a_shift_must_end_after_it_starts(newcomer):
    with pytest.raises(IntegrityError), transaction.atomic():
        Shift.objects.create(
            employee=newcomer, weekday=MONDAY, start_time=time(12), end_time=time(9)
        )


@pytest.mark.django_db
def test_deleting_an_employee_deletes_their_shifts(employee):
    employee.delete()

    assert not Shift.objects.exists()


# --- declare_shift -----------------------------------------------------------


@pytest.mark.django_db
def test_declare_shift_records_the_shift(newcomer):
    shift = declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )

    assert shift.employee == newcomer
    assert (shift.weekday, shift.start_time, shift.end_time) == (
        MONDAY,
        time(9),
        time(12),
    )


@pytest.mark.django_db
def test_declare_shift_rejects_an_end_before_the_start(newcomer):
    with pytest.raises(BookingError):
        declare_shift(
            employee=newcomer, weekday=MONDAY, start_time=time(12), end_time=time(9)
        )


@pytest.mark.django_db
def test_declare_shift_rejects_an_empty_shift(newcomer):
    with pytest.raises(BookingError):
        declare_shift(
            employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(9)
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("start", "end"),
    [(time(9, 15), time(12)), (time(9), time(11, 45))],
    ids=["start", "end"],
)
def test_declare_shift_rejects_times_off_the_slot_grid(newcomer, start, end):
    """A 9:15 start at a 30-minute office would silently lose a quarter of an
    hour: the slots are 9:00 and 9:30, and 9:15-9:30 fits neither."""
    with pytest.raises(BookingError):
        declare_shift(employee=newcomer, weekday=MONDAY, start_time=start, end_time=end)


@pytest.mark.django_db
def test_declare_shift_follows_the_office_slot_duration(office, newcomer):
    office.slot_duration_minutes = 60
    office.save()

    with pytest.raises(BookingError):
        declare_shift(
            employee=newcomer, weekday=MONDAY, start_time=time(9, 30), end_time=time(12)
        )


@pytest.mark.django_db
def test_declare_shift_rejects_an_overlap_with_the_same_employee(newcomer):
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )

    with pytest.raises(BookingError):
        declare_shift(
            employee=newcomer, weekday=MONDAY, start_time=time(11), end_time=time(14)
        )


@pytest.mark.django_db
def test_declare_shift_accepts_two_shifts_on_the_same_day(newcomer):
    """A morning and an afternoon, touching nothing: the lunch break."""
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(14), end_time=time(17)
    )

    assert newcomer.shifts.count() == 2


@pytest.mark.django_db
def test_declare_shift_accepts_back_to_back_shifts(newcomer):
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(12), end_time=time(14)
    )

    assert newcomer.shifts.count() == 2


@pytest.mark.django_db
def test_declare_shift_ignores_colleagues_shifts(office, employee):
    """Overlap is a rule about one person's week: colleagues on duty at the
    same time is exactly how an office covers a slot twice."""
    colleague = make_employee(office, "luca.verdi@unibo.it", shifts=[])

    declare_shift(
        employee=colleague, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )

    assert colleague.shifts.count() == 1


# --- availability derived from shifts (FR4, FR5) ------------------------------


@pytest.mark.django_db
def test_availability_covers_exactly_a_declared_shift(office, newcomer, day):
    """FR4's acceptance criterion: Monday 9:00-12:00 with 30-minute slots
    yields contiguous slots covering the whole shift, and nothing else."""
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )

    assert available_slots(office, day) == [
        slot_at(day, 9),
        slot_at(day, 9, 30),
        slot_at(day, 10),
        slot_at(day, 10, 30),
        slot_at(day, 11),
        slot_at(day, 11, 30),
    ]


@pytest.mark.django_db
def test_availability_is_the_union_of_the_office_shifts(office, day):
    make_employee(office, "a@unibo.it", shifts=[(MONDAY, time(9), time(10))])
    make_employee(office, "b@unibo.it", shifts=[(MONDAY, time(14), time(15))])

    assert available_slots(office, day) == [
        slot_at(day, 9),
        slot_at(day, 9, 30),
        slot_at(day, 14),
        slot_at(day, 14, 30),
    ]


@pytest.mark.django_db
def test_availability_ignores_other_offices_shifts(office, other_office, day):
    make_employee(other_office, "altrove@unibo.it")

    assert available_slots(office, day) == []


@pytest.mark.django_db
def test_availability_is_empty_on_a_day_nobody_works(office, newcomer, day):
    declare_shift(
        employee=newcomer, weekday=MONDAY + 1, start_time=time(9), end_time=time(12)
    )

    assert available_slots(office, day) == []


@pytest.mark.django_db
def test_a_new_shift_shows_up_at_once(office, newcomer, day):
    """FR5: slots are derived, not stored, so there is nothing to refresh."""
    assert available_slots(office, day) == []

    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(10)
    )

    assert available_slots(office, day) == [slot_at(day, 9), slot_at(day, 9, 30)]


@pytest.mark.django_db
def test_a_withdrawn_shift_disappears_at_once(office, newcomer, day):
    shift = declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(10)
    )

    withdraw_shift(shift)

    assert available_slots(office, day) == []


@pytest.mark.django_db
def test_availability_keeps_only_slots_a_shift_covers_whole(office, day):
    """A shift declared at 30-minute slots stays put if the office moves to
    60: it offers the hours it fully covers and nothing past its end."""
    make_employee(office, "a@unibo.it", shifts=[(MONDAY, time(9, 30), time(12))])
    office.slot_duration_minutes = 60
    office.save()

    assert available_slots(office, day) == [slot_at(day, 10), slot_at(day, 11)]


@pytest.mark.django_db
def test_a_slot_stays_available_while_someone_on_duty_is_free(office, student, day):
    """Capacity is counted per slot: two employees at 9, one at 10."""
    make_employee(office, "a@unibo.it", shifts=[(MONDAY, time(9), time(11))])
    make_employee(office, "b@unibo.it", shifts=[(MONDAY, time(9), time(10))])

    book(student, office, slot_at(day, 9))
    book(student, office, slot_at(day, 10))

    slots = available_slots(office, day)
    assert slot_at(day, 9) in slots
    assert slot_at(day, 10) not in slots


# --- who takes a booking -----------------------------------------------------


@pytest.mark.django_db
def test_a_booking_goes_to_someone_on_duty(office, student, day):
    """The least busy employee is only a candidate while on duty: here the
    idle one is off at 10, so the one already carrying work takes it."""
    busy = make_employee(office, "a@unibo.it", shifts=[(MONDAY, time(9), time(11))])
    make_employee(office, "b@unibo.it", shifts=[(MONDAY, time(14), time(17))])
    book(student, office, slot_at(day, 9))

    appointment = book(student, office, slot_at(day, 10))

    assert appointment.employee == busy


@pytest.mark.django_db
def test_book_appointment_rejects_a_slot_nobody_covers(office, newcomer, student, day):
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )

    with pytest.raises(BookingError):
        book(student, office, slot_at(day, 14))


@pytest.mark.django_db
def test_book_appointment_rejects_a_slot_running_past_the_shift(
    office, newcomer, student, day
):
    """11:30 is on the grid, but a 60-minute meeting there would end at 12:30,
    after the shift."""
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )
    office.slot_duration_minutes = 60
    office.save()

    with pytest.raises(BookingError):
        book(student, office, slot_at(day, 11, 30))


# --- withdraw_shift ----------------------------------------------------------


@pytest.mark.django_db
def test_withdraw_shift_deletes_it(newcomer):
    shift = declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )

    withdraw_shift(shift)

    assert not Shift.objects.exists()


@pytest.mark.django_db
def test_withdraw_shift_refuses_while_it_covers_a_booked_appointment(
    office, employee, student, day
):
    appointment = book(student, office, slot_at(day, 10))
    monday = employee.shifts.get(weekday=MONDAY)

    with pytest.raises(ShiftInUseError) as refused:
        withdraw_shift(monday)

    assert refused.value.appointments == [appointment]
    assert Shift.objects.filter(pk=monday.pk).exists()


@pytest.mark.django_db
def test_withdraw_shift_is_allowed_once_the_appointment_is_cancelled(
    office, employee, student, day
):
    cancel_appointment(book(student, office, slot_at(day, 10)), by=student)
    monday = employee.shifts.get(weekday=MONDAY)

    withdraw_shift(monday)

    assert not employee.shifts.filter(weekday=MONDAY).exists()


@pytest.mark.django_db
def test_withdraw_shift_ignores_appointments_outside_it(office, newcomer, student, day):
    morning = declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(9), end_time=time(12)
    )
    declare_shift(
        employee=newcomer, weekday=MONDAY, start_time=time(14), end_time=time(17)
    )
    book(student, office, slot_at(day, 14))

    withdraw_shift(morning)

    assert newcomer.shifts.count() == 1


@pytest.mark.django_db
def test_withdraw_shift_ignores_appointments_on_other_weekdays(
    office, employee, student, day
):
    book(student, office, slot_at(day + timedelta(days=1), 10))  # Tuesday

    withdraw_shift(employee.shifts.get(weekday=MONDAY))

    assert not employee.shifts.filter(weekday=MONDAY).exists()


@pytest.mark.django_db
def test_withdraw_shift_ignores_past_appointments(office, employee, student, day):
    """Last week's meeting already happened: the shift no longer holds it up."""
    Appointment.objects.create(
        student=student,
        office=office,
        employee=employee,
        slot=slot_at(day - timedelta(days=7), 10),
        status=AppointmentStatus.BOOKED,
        question_text="Domanda della settimana scorsa.",
        question_lang="it",
    )

    withdraw_shift(employee.shifts.get(weekday=MONDAY))

    assert not employee.shifts.filter(weekday=MONDAY).exists()


@pytest.mark.django_db
def test_withdraw_shift_ignores_colleagues_appointments(office, employee, day):
    colleague = make_employee(office, "luca.verdi@unibo.it")
    student = make_user("lucia.neri@studio.unibo.it", User.Role.STUDENT)
    # The least busy employee breaks ties on pk, so this one goes to `employee`.
    book(student, office, slot_at(day, 10))

    withdraw_shift(colleague.shifts.get(weekday=MONDAY))

    assert not colleague.shifts.filter(weekday=MONDAY).exists()
