"""Tests for the ``seed_offices`` management command."""

from io import StringIO

import pytest
from django.core.management import call_command

from booking.management.commands.seed_offices import OFFICES
from booking.models import Office
from pronto.enums import OfficeCode


def seed_offices():
    out = StringIO()
    call_command("seed_offices", stdout=out)
    return out.getvalue()


def test_every_office_code_has_the_data_to_seed_it():
    """A code added to `OfficeCode` without an entry here would never exist."""
    assert set(OFFICES) == set(OfficeCode)


@pytest.mark.django_db
def test_seed_offices_creates_one_active_office_per_code():
    output = seed_offices()

    assert "Created: 4" in output
    offices = {office.code: office for office in Office.objects.all()}
    assert set(offices) == set(OfficeCode.values)
    guidance = offices[OfficeCode.GUIDANCE]
    assert guidance.name_it == "Orientamento"
    assert guidance.name_en == "Guidance and Admissions"
    assert guidance.contact_email == "orientamento@unibo.it"
    assert all(office.slot_duration_minutes == 30 for office in offices.values())
    assert all(office.is_active for office in offices.values())


@pytest.mark.django_db
def test_seed_offices_twice_creates_nothing_more():
    seed_offices()

    output = seed_offices()

    assert "Created: 0" in output
    assert "Already there: 4" in output
    assert Office.objects.count() == len(OfficeCode)


@pytest.mark.django_db
def test_seed_offices_leaves_an_office_changed_in_the_admin_alone(office):
    """The `office` fixture is Guidance, with its own address and names."""
    office.contact_email = "orientamento.nuovo@unibo.it"
    office.slot_duration_minutes = 20
    office.save()

    output = seed_offices()

    assert "Created: 3" in output
    office.refresh_from_db()
    assert office.contact_email == "orientamento.nuovo@unibo.it"
    assert office.slot_duration_minutes == 20
