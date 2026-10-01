"""Tests for the office model.

`office` comes from `tests/conftest.py`. What links to an office — staff,
appointments, FAQs — is tested with the app that links to it.
"""

import pytest
from django.db import IntegrityError

from offices.models import Office
from pronto.enums import OfficeCode


def test_office_codes_come_from_the_shared_enum():
    assert Office._meta.get_field("code").choices == OfficeCode.choices


@pytest.mark.django_db
def test_a_new_office_is_active_and_books_half_hour_slots():
    # Created here rather than taken from conftest: the shared fixture sets
    # slot_duration_minutes explicitly, which would hide the default.
    office = Office.objects.create(
        code=OfficeCode.GUIDANCE,
        name_it="Orientamento",
        name_en="Guidance",
        contact_email="orientamento@unibo.it",
    )

    assert office.is_active
    assert office.slot_duration_minutes == 30


@pytest.mark.django_db
def test_an_office_is_displayed_by_its_italian_name(office):
    assert str(office) == "Orientamento"


@pytest.mark.django_db
def test_two_offices_cannot_share_a_code(office):
    with pytest.raises(IntegrityError):
        Office.objects.create(
            code=OfficeCode.GUIDANCE,
            name_it="Orientamento (bis)",
            name_en="Guidance (bis)",
            contact_email="altro@unibo.it",
        )
