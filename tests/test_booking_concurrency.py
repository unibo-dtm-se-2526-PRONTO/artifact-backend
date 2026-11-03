"""Tests for the booking rules under simultaneous requests (NFR1).

Threads with their own connections. Marked `postgres` (SQLite locks the
whole database) and `transaction=True` so the threads see each other's writes.
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
    cancel_appointment,
    declare_shift,
    withdraw_shift,
)
from tests.conftest import make_employee, make_user, slot_at

User = get_user_model()

pytestmark = [pytest.mark.postgres, pytest.mark.django_db(transaction=True)]


def run_together(*calls):
    """Run `calls` in threads released together by a barrier.

    Returns what each one returned or raised, in order.
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
    """More students than employees on duty ask for the same slot at once."""
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
    """Two overlapping shifts declared at once: one is recorded, one refused."""
    employee = make_employee(office, shifts=[])

    def declaring(start, end):
        # A fresh instance per thread.
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
    """The shift is withdrawn after the booking picks its employee, before insert.

    The booking must notice that its employee is no longer on duty.
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

    The lock on the employee makes it wait, then refuse.
    """
    employee = make_employee(office, shifts=[(day.weekday(), time(9), time(17))])
    shift = employee.shifts.get()
    student = make_user("mario.rossi@studio.unibo.it", User.Role.STUDENT)
    slot = slot_at(day, 10)

    inserted = threading.Event()
    appointment_booked = notifications.appointment_booked

    def notify_after_a_pause(appointment):
        inserted.set()
        # The withdrawal is blocked by the lock, so it cannot set an event.
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


# --- cancel_appointment ------------------------------------------------------


def test_simultaneous_cancellations_send_the_emails_once(office, day, monkeypatch):
    """A student cancels the same appointment twice at once (double click).

    One call cancels, the other is refused, and nobody is told twice.
    """
    make_employee(office)
    student = make_user("mario.rossi@studio.unibo.it", User.Role.STUDENT)
    booked = book_appointment(
        student=student,
        office=office,
        slot=slot_at(day, 10),
        question_text="Vorrei informazioni sul piano di studi.",
        question_lang="it",
    )

    notified = []
    appointment_cancelled = notifications.appointment_cancelled

    def notify_after_a_pause(appointment, by):
        notified.append(appointment.pk)
        pytime.sleep(0.5)
        appointment_cancelled(appointment, by=by)

    monkeypatch.setattr(notifications, "appointment_cancelled", notify_after_a_pause)

    def cancelling(instance):
        return lambda: cancel_appointment(instance, by=student)

    outcomes = run_together(
        cancelling(Appointment.objects.get(pk=booked.pk)),
        cancelling(Appointment.objects.get(pk=booked.pk)),
    )

    assert sum(isinstance(outcome, Appointment) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, BookingError) for outcome in outcomes) == 1
    assert notified == [booked.pk]
