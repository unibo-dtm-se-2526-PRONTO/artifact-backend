"""Tests for the booking rules under simultaneous requests (NFR1).

The other booking tests run one request at a time, so they cannot tell a rule
the database enforces from one that only holds while nobody else is writing.
Here several threads call the same service at once, each on its own database
connection and in its own transaction, as concurrent HTTP requests would.

They are marked `postgres`: SQLite locks the whole database on every write, so
the requests would be serialised and the tests would pass for the wrong reason.
They also need `transaction=True`, since the default test transaction would
hide each thread's writes from the others until the end of the test.
"""

import threading
import time as pytime
from datetime import time

import pytest
from django.contrib.auth import get_user_model
from django.db import connection

from booking import notifications, services
from booking.models import Appointment, EmployeeProfile, Shift
from booking.services import (
    BookingError,
    ShiftInUseError,
    book_appointment,
    declare_shift,
    withdraw_shift,
)
from tests.conftest import make_employee, make_user, slot_at

User = get_user_model()

pytestmark = [pytest.mark.postgres, pytest.mark.django_db(transaction=True)]


def run_together(*calls):
    """Run each of `calls` in its own thread, all released at the same moment.

    Returns, in the order of `calls`, what each one returned or the exception
    it raised. A barrier holds every thread until all of them are ready, so
    the calls overlap instead of running one after the other as the threads
    happen to start. Each thread closes its connection when done: Django opens
    one per thread, and a connection left open would keep the test database
    from being flushed.
    """
    barrier = threading.Barrier(len(calls), timeout=10)
    outcomes = [None] * len(calls)

    def run(index, call):
        try:
            barrier.wait()
            outcomes[index] = call()
        except Exception as error:  # noqa: BLE001 - the outcome is the error
            outcomes[index] = error
        finally:
            connection.close()

    threads = [
        threading.Thread(target=run, args=(index, call))
        for index, call in enumerate(calls)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads), "a call never returned"
    return outcomes


# --- book_appointment --------------------------------------------------------


def test_simultaneous_bookings_never_double_book_an_employee(office, day):
    """More students than employees on duty ask for the same slot at once.

    Every employee on duty ends up with exactly one appointment, and every
    other student is told the slot is gone: the partial unique index settles
    each lost race, and seq2 moves the loser on to a colleague still free.
    """
    employees = [make_employee(office, email=f"employee{n}@unibo.it") for n in range(3)]
    students = [
        make_user(f"student{n}@studio.unibo.it", User.Role.STUDENT) for n in range(8)
    ]
    slot = slot_at(day, 10)

    def booking_for(student):
        return lambda: book_appointment(
            student=student,
            office=office,
            slot=slot,
            question_text="Vorrei informazioni sul piano di studi.",
            question_lang="it",
        )

    outcomes = run_together(*(booking_for(student) for student in students))

    booked = [outcome for outcome in outcomes if isinstance(outcome, Appointment)]
    refused = [outcome for outcome in outcomes if isinstance(outcome, BookingError)]
    assert len(booked) == len(employees)
    assert len(refused) == len(students) - len(employees)
    assert {appointment.employee_id for appointment in booked} == {
        employee.pk for employee in employees
    }
    assert Appointment.objects.filter(slot=slot).count() == len(employees)


# --- declare_shift -----------------------------------------------------------


def test_simultaneous_overlapping_shifts_are_not_both_declared(office):
    """Two overlapping shifts declared at once: one is recorded, one refused.

    Each call checks for overlaps before inserting, so without the lock on the
    employee both checks could pass before either insert.
    """
    employee = make_employee(office, shifts=[])

    def declaring(start, end):
        # A fresh instance per thread: model instances are not meant to be
        # shared across threads, and each call reads the employee's office.
        return lambda: declare_shift(
            employee=EmployeeProfile.objects.get(pk=employee.pk),
            weekday=0,
            start_time=start,
            end_time=end,
        )

    outcomes = run_together(
        declaring(time(9), time(12)),
        declaring(time(11), time(13)),
    )

    assert sum(isinstance(outcome, Shift) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, BookingError) for outcome in outcomes) == 1
    assert employee.shifts.count() == 1


# --- withdraw_shift against book_appointment ---------------------------------


def test_a_shift_withdrawn_mid_booking_leaves_no_appointment_uncovered(
    office, day, monkeypatch
):
    """The shift goes after the booking has picked its employee, before insert.

    Left to chance this interleaving is rare, so the test forces it: the
    booking pauses right after choosing the employee, and the withdrawal runs
    to completion in that gap. The withdrawal finds nothing booked and
    succeeds; the booking must then notice that its employee is no longer on
    duty, rather than insert an appointment no shift covers — the very state
    `withdraw_shift` exists to refuse.
    """
    employee = make_employee(office, shifts=[(day.weekday(), time(9), time(17))])
    shift = employee.shifts.get()
    student = make_user("mario.rossi@studio.unibo.it", User.Role.STUDENT)
    slot = slot_at(day, 10)

    chosen = threading.Event()
    withdrawn = threading.Event()
    free_employee = services._free_employee

    def free_employee_then_pause(office, slot):
        found = free_employee(office, slot)
        if not chosen.is_set():
            chosen.set()
            withdrawn.wait(timeout=5)
        return found

    monkeypatch.setattr(services, "_free_employee", free_employee_then_pause)

    def booking():
        return book_appointment(
            student=student,
            office=office,
            slot=slot,
            question_text="Vorrei informazioni sul piano di studi.",
            question_lang="it",
        )

    def withdrawal():
        assert chosen.wait(timeout=5), "the booking never chose an employee"
        try:
            return withdraw_shift(Shift.objects.get(pk=shift.pk))
        finally:
            withdrawn.set()

    booked, withdraw_outcome = run_together(booking, withdrawal)

    assert withdraw_outcome is None
    assert not Shift.objects.filter(pk=shift.pk).exists()
    assert isinstance(booked, BookingError)
    assert not Appointment.objects.filter(slot=slot).exists()


def test_a_shift_cannot_be_withdrawn_under_a_booking_not_yet_committed(
    office, day, monkeypatch
):
    """The withdrawal comes after the insert, before the booking commits.

    The appointment is not visible to other transactions yet, so the check in
    `withdraw_shift` would find nothing held and delete the shift. The lock on
    the employee makes the withdrawal wait for the booking to commit, and then
    it sees the appointment and refuses. The booking pauses inside its
    transaction — in the notification call, the last step before the commit —
    long enough for the withdrawal to reach the lock.
    """
    employee = make_employee(office, shifts=[(day.weekday(), time(9), time(17))])
    shift = employee.shifts.get()
    student = make_user("mario.rossi@studio.unibo.it", User.Role.STUDENT)
    slot = slot_at(day, 10)

    inserted = threading.Event()
    appointment_booked = notifications.appointment_booked

    def notify_after_a_pause(appointment):
        inserted.set()
        # Not an event the withdrawal sets: with the lock in place it is
        # blocked until this transaction ends, so it could never set it.
        pytime.sleep(0.5)
        appointment_booked(appointment)

    monkeypatch.setattr(notifications, "appointment_booked", notify_after_a_pause)

    def booking():
        return book_appointment(
            student=student,
            office=office,
            slot=slot,
            question_text="Vorrei informazioni sul piano di studi.",
            question_lang="it",
        )

    def withdrawal():
        assert inserted.wait(timeout=5), "the booking never inserted"
        return withdraw_shift(Shift.objects.get(pk=shift.pk))

    booked, withdraw_outcome = run_together(booking, withdrawal)

    assert isinstance(booked, Appointment)
    assert isinstance(withdraw_outcome, ShiftInUseError)
    assert withdraw_outcome.appointments == [booked]
    assert Shift.objects.filter(pk=shift.pk).exists()
