"""Fixtures shared by more than one test file.

A fixture moves here once a second file needs it. The booking slice is tested
from several angles — models, constraints, services, offices and appointments —
and all of them need the same cast: an office, someone staffing it, a student,
and a day in the future that is not a weekend. The accounts and FAQ tests share
less: an anonymous `client`, the `PASSWORD` every test user has, and
`authenticate` to give a user a token. FAQs and questions are filed under an
office: `office_for` gives the one with a code, creating it if needed.

Every employee made here works Monday to Friday, 9 to 17, unless a test asks
for other shifts. That is the timetable the helpdesk had before shifts existed,
so the booking tests written against it still describe a real office.

Fixture names are deliberately specific (`office`, `student`, `employee`)
rather than generic, so nothing here shadows what another test file defines
for itself. `client` is the exception, and on purpose: it replaces
pytest-django's fixture of the same name with DRF's `APIClient`, a subclass of
Django's test client that also speaks JSON (`format="json"`).

It also holds the one hook every test file relies on: tests marked
`@pytest.mark.postgres` are skipped unless the suite runs on PostgreSQL.
"""

from datetime import datetime, time, timedelta
from itertools import count

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import StudentProfile
from booking.models import EmployeeProfile, Shift
from offices.models import Office
from offices.seed import seed_office
from pronto.enums import OfficeCode

User = get_user_model()

PASSWORD = "s3cret-passphrase"


def pytest_collection_modifyitems(config, items):
    """Skip the tests marked `postgres` when the database is not PostgreSQL.

    Some behaviour cannot be observed on SQLite at all — full-text search does
    not exist there, and it locks the whole database rather than a row — so a
    test of it would fail for the wrong reason. Skipping says so in the report
    instead. `connection.vendor` comes from the configured backend and needs no
    connection, so this runs before any test touches the database.
    """
    if connection.vendor == "postgresql":
        return
    skip = pytest.mark.skip(reason="needs PostgreSQL: set TEST_DATABASE_URL")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip)


# Monday to Friday, as weekday() numbers them, nine to five.
WORKING_WEEK = [(weekday, time(9), time(17)) for weekday in range(5)]


def next_working_day():
    """The next Monday: always a weekday, always in the future."""
    today = timezone.localtime(timezone.now()).date()
    return today + timedelta(days=(7 - today.weekday()) or 7)


def slot_at(day, hour, minute=0):
    """An aware datetime for `day` at `hour`:`minute`."""
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


# Matricole for the students a test does not give one: unique, and well formed.
matricole = (f"{n:010d}" for n in count(1))


def make_user(email, role, **fields):
    """An active user; `fields` sets anything else, such as the names.

    A student also gets the student profile registration would have given
    them, from the `matricola` and `degree_programme` in `fields`, or made up.
    """
    student = {
        key: fields.pop(key)
        for key in ("matricola", "degree_programme")
        if key in fields
    }
    user = User.objects.create_user(
        email=email, password=PASSWORD, role=role, is_active=True, **fields
    )
    if role == User.Role.STUDENT:
        StudentProfile.objects.create(
            user=user,
            matricola=student.get("matricola") or next(matricole),
            degree_programme=student.get(
                "degree_programme", "Ingegneria e scienze informatiche"
            ),
        )
    return user


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


def office_for(code):
    """The office with `code`; if there is none yet, it is created as
    `seed_offices` would create it."""
    return seed_office(Office, code)[0]


def authenticate(user):
    """An APIClient carrying `user`'s token."""
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
    )
    return client


@pytest.fixture
def client():
    """An anonymous API client, for the endpoints called before logging in."""
    return APIClient()


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
