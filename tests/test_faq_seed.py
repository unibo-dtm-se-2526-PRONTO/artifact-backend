"""Tests for the bundled FAQs and the ``seed_faqs`` management command."""

from io import StringIO

import pytest
from django.core.management import call_command

from faq import vector_index
from faq.anonymisation import anonymise
from faq.models import Faq
from faq.seed import load_faqs
from offices.models import Office
from pronto.enums import OfficeCode
from tests.test_faq_semantic import (  # noqa: F401 (fixtures)
    store_down,
    stored_ids,
    vector_store,
)

TEXT_FIELDS = ("question_it", "question_en", "answer_it", "answer_en")


def seed_faqs():
    out = StringIO()
    call_command("seed_faqs", stdout=out)
    return out.getvalue()


# --- the bundled data ---------------------------------------------------------


def test_the_bundled_faqs_are_the_helpdesk_spreadsheet():
    faqs = load_faqs()

    assert len(faqs) == 179
    assert {faq["office"] for faq in faqs} == set(OfficeCode.values)
    assert all(faq[field] for faq in faqs for field in TEXT_FIELDS)


def test_the_bundled_faqs_have_one_entry_per_office_and_question():
    keys = [(faq["office"], faq["question_it"]) for faq in load_faqs()]

    assert len(keys) == len(set(keys))


def test_the_bundled_faqs_are_anonymised():
    assert all(
        anonymise(faq[field]) == faq[field]
        for faq in load_faqs()
        for field in TEXT_FIELDS
    )


# --- seeding ------------------------------------------------------------------


@pytest.mark.django_db
def test_seed_faqs_publishes_every_bundled_faq_under_its_office():
    output = seed_faqs()

    assert "Created: 179" in output
    assert Faq.objects.filter(is_active=True).count() == 179
    assert set(Office.objects.values_list("code", flat=True)) == set(OfficeCode.values)
    first = load_faqs()[0]
    faq = Faq.objects.get(
        office__code=first["office"], question_it=first["question_it"]
    )
    assert [getattr(faq, field) for field in TEXT_FIELDS] == [
        first[field] for field in TEXT_FIELDS
    ]


@pytest.mark.django_db
def test_seed_faqs_twice_creates_nothing_more():
    seed_faqs()

    output = seed_faqs()

    assert "Created: 0" in output
    assert "Already there: 179" in output
    assert Faq.objects.count() == 179


@pytest.mark.django_db
def test_seed_faqs_leaves_a_faq_changed_in_the_admin_alone():
    seed_faqs()
    first = load_faqs()[0]
    faq = Faq.objects.get(
        office__code=first["office"], question_it=first["question_it"]
    )
    faq.answer_it = "Risposta corretta dall'ufficio."
    faq.is_active = False
    faq.save()

    seed_faqs()

    faq.refresh_from_db()
    assert faq.answer_it == "Risposta corretta dall'ufficio."
    assert not faq.is_active


@pytest.mark.django_db
def test_seed_faqs_indexes_the_new_faqs(vector_store):  # noqa: F811
    output = seed_faqs()

    assert len(stored_ids(vector_store)) == 2 * 179
    assert "Indexed: 179 FAQs" in output


@pytest.mark.django_db
def test_seed_faqs_does_not_index_again_when_nothing_is_new(
    monkeypatch,
    vector_store,  # noqa: F811
):
    seed_faqs()
    monkeypatch.setattr(vector_index, "rebuild", pytest.fail)

    seed_faqs()


@pytest.mark.django_db
def test_seed_faqs_keeps_the_faqs_when_the_vector_store_is_down(
    store_down,  # noqa: F811
):
    output = seed_faqs()

    assert Faq.objects.count() == 179
    assert "rebuild_faq_index" in output
