"""Tests for the FAQ model."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from faq.models import Faq
from pronto.enums import OfficeCode


def faq(**overrides):
    """A valid, unsaved FAQ; pass keyword arguments to vary one field."""
    fields = {
        "office_code": OfficeCode.GUIDANCE,
        "question_it": "Come mi iscrivo a un appello?",
        "question_en": "How do I sign up for an exam?",
        "answer_it": "Dalla sezione Esami di Studenti Online.",
        "answer_en": "From the Exams section of Studenti Online.",
    }
    return Faq(**{**fields, **overrides})


def test_office_code_choices_come_from_the_shared_enum():
    # The contract with the booking app: faq has no foreign key to Office, so
    # the enum is the only thing keeping the two slices in agreement.
    assert Faq._meta.get_field("office_code").choices == OfficeCode.choices


@pytest.mark.django_db
def test_a_faq_is_stored_with_both_languages():
    faq().save()

    stored = Faq.objects.get()
    assert stored.question_it == "Come mi iscrivo a un appello?"
    assert stored.question_en == "How do I sign up for an exam?"
    assert stored.answer_it == "Dalla sezione Esami di Studenti Online."
    assert stored.answer_en == "From the Exams section of Studenti Online."


@pytest.mark.django_db
def test_a_new_faq_is_active_by_default():
    faq().save()

    assert Faq.objects.get().is_active


@pytest.mark.django_db
def test_creation_and_update_timestamps_are_set_automatically():
    stored = faq()
    stored.save()

    assert stored.created_at is not None
    assert stored.updated_at is not None


@pytest.mark.django_db
def test_updating_a_faq_moves_the_updated_timestamp_forward():
    stored = faq()
    stored.save()
    first_update = stored.updated_at

    stored.answer_it = "Dalla sezione Esami, almeno cinque giorni prima."
    stored.save()

    assert stored.updated_at > first_update


@pytest.mark.django_db
def test_faqs_are_ordered_by_office_then_question():
    faq(office_code=OfficeCode.INTERNSHIPS, question_it="Zeta?").save()
    faq(office_code=OfficeCode.ADMIN_OFFICE, question_it="Beta?").save()
    faq(office_code=OfficeCode.ADMIN_OFFICE, question_it="Alfa?").save()

    assert [(f.office_code, f.question_it) for f in Faq.objects.all()] == [
        (OfficeCode.ADMIN_OFFICE, "Alfa?"),
        (OfficeCode.ADMIN_OFFICE, "Beta?"),
        (OfficeCode.INTERNSHIPS, "Zeta?"),
    ]


@pytest.mark.django_db
def test_the_same_question_can_be_filed_under_two_different_offices():
    faq(office_code=OfficeCode.GUIDANCE).save()

    faq(office_code=OfficeCode.INTERNSHIPS).save()

    assert Faq.objects.count() == 2


def test_an_unknown_office_code_is_rejected_by_validation():
    # Only full_clean() enforces choices: the database column is a plain
    # CharField, so a bad value would otherwise be stored happily.
    with pytest.raises(ValidationError):
        faq(office_code="CANTEEN").full_clean()


@pytest.mark.django_db
def test_the_same_question_cannot_be_filed_twice_under_one_office():
    faq().save()

    with pytest.raises(IntegrityError):
        faq().save()


@pytest.mark.django_db
def test_a_faq_is_displayed_as_its_office_and_italian_question():
    stored = faq()

    assert str(stored) == "[GUIDANCE] Come mi iscrivo a un appello?"
