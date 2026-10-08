"""Tests for the FAQ model."""

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from faq.models import Faq, Inquiry
from pronto.enums import OfficeCode
from tests.conftest import office_for


def faq(**overrides):
    """A valid, unsaved FAQ, filed under Guidance unless `office` says
    otherwise; pass keyword arguments to vary one field."""
    if "office" not in overrides:
        overrides["office"] = office_for(OfficeCode.GUIDANCE)
    fields = {
        "question_it": "Come mi iscrivo a un appello?",
        "question_en": "How do I sign up for an exam?",
        "answer_it": "Dalla sezione Esami di Studenti Online.",
        "answer_en": "From the Exams section of Studenti Online.",
    }
    return Faq(**{**fields, **overrides})


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
    # Two saves in a row can read the same clock tick — on Windows the clock
    # is coarse enough that they often do — and the timestamp would then stay
    # put. Moving the first one back an hour makes "forward" observable
    # whatever the clock's resolution. `update()` skips auto_now, so the value
    # written is the one given.
    first_update = stored.updated_at - timedelta(hours=1)
    Faq.objects.filter(pk=stored.pk).update(updated_at=first_update)
    stored.refresh_from_db()

    stored.answer_it = "Dalla sezione Esami, almeno cinque giorni prima."
    stored.save()

    assert stored.updated_at > first_update


@pytest.mark.django_db
def test_faqs_are_ordered_by_office_then_question():
    faq(office=office_for(OfficeCode.INTERNSHIPS), question_it="Zeta?").save()
    faq(office=office_for(OfficeCode.ADMIN_OFFICE), question_it="Beta?").save()
    faq(office=office_for(OfficeCode.ADMIN_OFFICE), question_it="Alfa?").save()

    assert [(f.office.code, f.question_it) for f in Faq.objects.all()] == [
        (OfficeCode.ADMIN_OFFICE, "Alfa?"),
        (OfficeCode.ADMIN_OFFICE, "Beta?"),
        (OfficeCode.INTERNSHIPS, "Zeta?"),
    ]


@pytest.mark.django_db
def test_the_same_question_can_be_filed_under_two_different_offices():
    faq(office=office_for(OfficeCode.GUIDANCE)).save()

    faq(office=office_for(OfficeCode.INTERNSHIPS)).save()

    assert Faq.objects.count() == 2


@pytest.mark.django_db
def test_an_office_with_faqs_cannot_be_deleted():
    stored = faq()
    stored.save()

    with pytest.raises(ProtectedError):
        stored.office.delete()


@pytest.mark.django_db
def test_an_office_with_questions_asked_about_it_cannot_be_deleted():
    office = office_for(OfficeCode.GUIDANCE)
    Inquiry.objects.create(office=office, text="Come mi iscrivo?", language="it")

    with pytest.raises(ProtectedError):
        office.delete()


@pytest.mark.django_db
def test_the_same_question_cannot_be_filed_twice_under_one_office():
    faq().save()

    with pytest.raises(IntegrityError):
        faq().save()


@pytest.mark.django_db
@pytest.mark.django_db
def test_a_faq_is_displayed_as_its_office_and_italian_question():
    stored = faq()

    assert str(stored) == "[GUIDANCE] Come mi iscrivo a un appello?"
