"""Fixtures shared by the booking tests.

The accounts tests keep their fixtures local, which works while one file owns
them. The booking slice is tested from several angles — models, constraints,
services, offices and appointments — and all of them need the same cast: an
office, someone staffing it, a student, and a day in the future that is not a
weekend.

Every employee made here works Monday to Friday, 9 to 17, unless a test asks
for other shifts. That is the timetable the helpdesk had before shifts existed,
so the booking tests written against it still describe a real office.

Fixture names are deliberately specific (`office`, `student`, `employee`)
rather than generic, so nothing here shadows what another test file defines
for itself.
"""

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from booking.models import EmployeeProfile, Office, Shift
from pronto.enums import OfficeCode

User = get_user_model()

PASSWORD = "s3cret-passphrase"

# Monday to Friday, as weekday() numbers them, nine to five.
WORKING_WEEK = [(weekday, time(9), time(17)) for weekday in range(5)]


def next_working_day():
    """The next Monday: always a weekday, always in the future."""
    today = timezone.localtime(timezone.now()).date()
    return today + timedelta(days=(7 - today.weekday()) or 7)


def slot_at(day, hour, minute=0):
    """An aware datetime for `day` at `hour`:`minute`."""
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def make_user(email, role):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=role, is_active=True
    )


def make_employee(office, email="anna.bianchi@unibo.it", shifts=WORKING_WEEK):
    """An employee of `office`, on duty for each ``(weekday, start, end)``.

    Shifts are written straight to the table: the rules for declaring them are
    what `test_booking_shifts.py` tests, not something every fixture should
    depend on.
    """
    employee = EmployeeProfile.objects.create(
        user=make_user(email, User.Role.EMPLOYEE), office=office
    )
    Shift.objects.bulk_create(
        Shift(employee=employee, weekday=weekday, start_time=start, end_time=end)
        for weekday, start, end in shifts
    )
    return employee


def authenticate(user):
    """An APIClient carrying `user`'s token."""
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
    )
    return client


@pytest.fixture
def day():
    return next_working_day()


@pytest.fixture
def office(db):
    return Office.objects.create(
        code=OfficeCode.GUIDANCE,
        name_it="Orientamento",
        name_en="Guidance",
        contact_email="orientamento@unibo.it",
        slot_duration_minutes=30,
    )


@pytest.fixture
def other_office(db):
    return Office.objects.create(
        code=OfficeCode.ADMIN_OFFICE,
        name_it="Segreteria studenti",
        name_en="Student office",
        contact_email="segreteria@unibo.it",
        slot_duration_minutes=30,
    )


@pytest.fixture
def employee(office):
    return make_employee(office)


@pytest.fixture
def student(db):
    return make_user("mario.rossi@studio.unibo.it", User.Role.STUDENT)


@pytest.fixture
def student_client(student):
    return authenticate(student)


@pytest.fixture
def employee_client(employee):
    return authenticate(employee.user)
