"""Fixtures shared by the booking tests.

The accounts tests keep their fixtures local, which works while one file owns
them. The booking slice is tested from several angles — models, constraints,
services, offices and appointments — and all of them need the same cast: an
office, someone staffing it, a student, and a day in the future that is not a
weekend.

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

from booking.models import EmployeeProfile, Office
from pronto.enums import OfficeCode

User = get_user_model()

PASSWORD = "s3cret-passphrase"


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


def make_employee(office, email="anna.bianchi@unibo.it"):
    return EmployeeProfile.objects.create(
        user=make_user(email, User.Role.EMPLOYEE), office=office
    )


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
