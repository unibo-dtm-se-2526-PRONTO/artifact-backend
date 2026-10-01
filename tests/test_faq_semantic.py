"""Tests for semantic FAQ matching: the vector store and its matcher (IR4).

No Chroma server and no embedding model: each test gets an in-memory Chroma
collection, and `fake_embed` stands in for the model. The fake knows a few
groups of words that mean the same thing ("certificato", "attestato") and
nothing else, which is enough to tell a FAQ worded differently from the
question apart from an unrelated one. How well the real model does that is a
matter of calibration, not of these tests.

Indexing, the matcher and the cascade run on SQLite. Only the tests that go
through `find_best_match`, where full-text search runs first, need PostgreSQL.
"""

import logging
import math
import re
from io import StringIO

import chromadb
import pytest
from django.core.management import CommandError, call_command
from rest_framework import status

from faq import vector_index
from faq.matching import (
    CascadeMatcher,
    Match,
    SemanticMatcher,
    find_best_match,
)
from faq.models import Faq, Inquiry, MatchMethod
from faq.services import ask_question
from pronto.enums import OfficeCode

# Words that mean the same thing share a concept; any other word is ignored.
CONCEPTS = {
    "certificato": "certificate",
    "attestato": "certificate",
    "certificate": "certificate",
    "iscrizione": "enrolment",
    "iscritto": "enrolment",
    "enrolment": "enrolment",
    "enrolled": "enrolment",
    "tasse": "fees",
    "contributi": "fees",
    "fees": "fees",
    "tirocinio": "internship",
    "stage": "internship",
    "internship": "internship",
}
DIMENSIONS = sorted(set(CONCEPTS.values()))


def fake_embed(texts):
    """A unit vector per text, one dimension per concept it mentions. The
    extra last dimension keeps a text without any concept from being the zero
    vector, which has no direction to compare."""
    vectors = []
    for text in texts:
        words = re.findall(r"\w+", text.lower())
        concepts = {CONCEPTS[word] for word in words if word in CONCEPTS}
        vector = [1.0 if concept in concepts else 0.0 for concept in DIMENSIONS]
        vector.append(0.1)
        norm = math.sqrt(sum(value * value for value in vector))
        vectors.append([value / norm for value in vector])
    return vectors


@pytest.fixture
def vector_store(monkeypatch):
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(
        vector_index.COLLECTION,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )
    monkeypatch.setattr(vector_index, "get_collection", lambda: collection)
    monkeypatch.setattr(vector_index, "embed", fake_embed)
    yield collection
    # In-memory clients share their state within a process.
    client.delete_collection(vector_index.COLLECTION)


@pytest.fixture
def store_down(monkeypatch):
    def unreachable():
        raise ValueError("Could not connect to a Chroma server.")

    monkeypatch.setattr(vector_index, "get_collection", unreachable)


def make_faq(office_code, question_it, question_en, is_active=True):
    return Faq.objects.create(
        office_code=office_code,
        question_it=question_it,
        question_en=question_en,
        answer_it="Dal portale Studenti Online.",
        answer_en="From the Studenti Online portal.",
        is_active=is_active,
    )


@pytest.fixture
def certificate(db, vector_store, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        return make_faq(
            OfficeCode.ADMIN_OFFICE,
            "Come richiedo un certificato di iscrizione?",
            "How do I request a certificate of enrolment?",
        )


@pytest.fixture
def internship(db, vector_store, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        return make_faq(
            OfficeCode.INTERNSHIPS,
            "Come attivo un tirocinio curriculare?",
            "How do I start a curricular internship?",
        )


def stored_ids(collection):
    return sorted(collection.get(include=[])["ids"])


def published():
    return Faq.objects.filter(is_active=True)


def call_command_output(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


# --- keeping the index in step ----------------------------------------------


@pytest.mark.django_db
def test_a_published_faq_is_indexed_in_both_languages(vector_store, certificate):
    entries = vector_store.get(include=["documents", "metadatas"])

    assert sorted(entries["ids"]) == [f"{certificate.pk}-en", f"{certificate.pk}-it"]
    assert set(entries["documents"]) == {
        certificate.question_it,
        certificate.question_en,
    }
    assert {entry["language"] for entry in entries["metadatas"]} == {"it", "en"}


@pytest.mark.django_db
def test_nothing_is_indexed_before_the_commit(
    vector_store, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=False):
        make_faq(OfficeCode.ADMIN_OFFICE, "Come pago le tasse?", "How do I pay fees?")

    assert vector_store.count() == 0


@pytest.mark.django_db
def test_an_unpublished_faq_is_not_indexed(
    vector_store, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        make_faq(
            OfficeCode.ADMIN_OFFICE,
            "Come pago le tasse?",
            "How do I pay fees?",
            is_active=False,
        )

    assert vector_store.count() == 0


@pytest.mark.django_db
def test_unpublishing_a_faq_removes_it(
    vector_store, certificate, django_capture_on_commit_callbacks
):
    certificate.is_active = False
    with django_capture_on_commit_callbacks(execute=True):
        certificate.save()

    assert vector_store.count() == 0


@pytest.mark.django_db
def test_deleting_a_faq_removes_it(
    vector_store, certificate, internship, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        certificate.delete()

    assert stored_ids(vector_store) == [f"{internship.pk}-en", f"{internship.pk}-it"]


@pytest.mark.django_db
def test_editing_a_question_updates_its_entry(
    vector_store, certificate, django_capture_on_commit_callbacks
):
    certificate.question_it = "Come ottengo un attestato di iscrizione?"
    with django_capture_on_commit_callbacks(execute=True):
        certificate.save()

    entry = vector_store.get(ids=[f"{certificate.pk}-it"], include=["documents"])
    assert entry["documents"] == ["Come ottengo un attestato di iscrizione?"]


@pytest.mark.django_db
def test_a_faq_is_saved_even_when_the_vector_store_is_down(
    store_down, caplog, django_capture_on_commit_callbacks
):
    with (
        caplog.at_level(logging.ERROR, logger="faq.signals"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        faq = make_faq(OfficeCode.ADMIN_OFFICE, "Come pago le tasse?", "How?")

    assert Faq.objects.filter(pk=faq.pk).exists()
    assert f"Could not update FAQ {faq.pk}" in caplog.text


@pytest.mark.django_db
def test_without_a_chroma_host_nothing_is_indexed(
    settings, monkeypatch, django_capture_on_commit_callbacks
):
    settings.CHROMA_HOST = ""

    def no_model(texts):
        raise AssertionError("nothing should be embedded")

    monkeypatch.setattr(vector_index, "embed", no_model)
    with django_capture_on_commit_callbacks(execute=True):
        make_faq(OfficeCode.ADMIN_OFFICE, "Come pago le tasse?", "How do I pay fees?")

    assert vector_index.get_collection() is None


# --- rebuilding ---------------------------------------------------------------


@pytest.mark.django_db
def test_rebuilding_indexes_every_published_faq_and_drops_the_rest(
    vector_store, certificate, internship
):
    # Changes that sent no signal: the index no longer matches the database.
    Faq.objects.filter(pk=internship.pk).update(is_active=False)
    fees = make_faq(
        OfficeCode.ADMIN_OFFICE, "Come pago le tasse?", "How do I pay fees?"
    )
    vector_store.delete(ids=vector_index.entry_ids(certificate.pk))

    out = call_command_output("rebuild_faq_index")

    assert stored_ids(vector_store) == sorted(
        vector_index.entry_ids(certificate.pk) + vector_index.entry_ids(fees.pk)
    )
    assert "Indexed: 2 FAQs" in out


@pytest.mark.django_db
def test_rebuilding_is_refused_when_semantic_matching_is_off(settings):
    settings.CHROMA_HOST = ""

    with pytest.raises(CommandError, match="CHROMA_HOST"):
        call_command("rebuild_faq_index")


@pytest.mark.django_db
def test_rebuilding_reports_an_unreachable_server(store_down):
    with pytest.raises(CommandError, match="not reachable"):
        call_command("rebuild_faq_index")


# --- the semantic matcher -----------------------------------------------------


@pytest.mark.django_db
def test_a_question_worded_differently_finds_its_faq(certificate):
    match = SemanticMatcher().best_match(
        "Mi serve un attestato: sono iscritto?", "it", published()
    )

    assert match is not None
    assert match.faq == certificate
    assert match.matched_by == MatchMethod.SEMANTIC
    assert match.score > 0.9


@pytest.mark.django_db
def test_an_unrelated_question_finds_nothing(certificate):
    assert (
        SemanticMatcher().best_match("Dove si trova la mensa?", "it", published())
        is None
    )


@pytest.mark.django_db
def test_only_the_entries_in_the_language_of_the_question_are_searched(
    vector_store, certificate
):
    vector_store.delete(ids=[f"{certificate.pk}-it"])

    assert (
        SemanticMatcher().best_match("Un attestato di iscrizione?", "it", published())
        is None
    )
    assert (
        SemanticMatcher().best_match("An enrolment certificate?", "en", published())
        is not None
    )


@pytest.mark.django_db
def test_only_the_candidates_are_searched(certificate, internship):
    candidates = published().filter(office_code=OfficeCode.INTERNSHIPS)

    assert (
        SemanticMatcher().best_match("Un attestato di iscrizione?", "it", candidates)
        is None
    )


@pytest.mark.django_db
def test_a_faq_unpublished_without_updating_the_index_is_not_suggested(certificate):
    Faq.objects.filter(pk=certificate.pk).update(is_active=False)

    assert (
        SemanticMatcher().best_match("Un attestato di iscrizione?", "it", published())
        is None
    )


@pytest.mark.django_db
def test_a_match_under_the_threshold_is_not_suggested(settings, certificate):
    match = SemanticMatcher().best_match(
        "Un attestato di iscrizione?", "it", published()
    )
    assert match is not None
    settings.FAQ_SEMANTIC_MIN_SIMILARITY = match.score + 0.001

    assert (
        SemanticMatcher().best_match("Un attestato di iscrizione?", "it", published())
        is None
    )


@pytest.mark.django_db
def test_with_the_vector_store_down_the_matcher_finds_nothing(
    certificate, store_down, caplog
):
    with caplog.at_level(logging.ERROR, logger="faq.matching"):
        match = SemanticMatcher().best_match(
            "Un attestato di iscrizione?", "it", published()
        )

    assert match is None
    assert "Semantic FAQ search failed" in caplog.text


@pytest.mark.django_db
def test_with_semantic_matching_off_the_matcher_finds_nothing(settings):
    settings.CHROMA_HOST = ""
    make_faq(OfficeCode.ADMIN_OFFICE, "Come richiedo un certificato?", "How?")

    assert (
        SemanticMatcher().best_match("Un attestato di iscrizione?", "it", published())
        is None
    )


# --- the cascade --------------------------------------------------------------


class StubMatcher:
    def __init__(self, match):
        self.match = match
        self.asked = 0

    def best_match(self, question, language, candidates):
        self.asked += 1
        return self.match


def a_match(faq, matched_by):
    return Match(faq=faq, score=0.5, matched_by=matched_by)


@pytest.mark.django_db
def test_the_first_matcher_that_finds_a_match_wins(certificate):
    first = StubMatcher(a_match(certificate, MatchMethod.FULL_TEXT))
    second = StubMatcher(a_match(certificate, MatchMethod.SEMANTIC))

    match = CascadeMatcher(first, second).best_match("?", "it", published())

    assert match == first.match
    assert second.asked == 0


@pytest.mark.django_db
def test_the_next_matcher_is_asked_when_one_finds_nothing(certificate):
    second = StubMatcher(a_match(certificate, MatchMethod.SEMANTIC))

    match = CascadeMatcher(StubMatcher(None), second).best_match("?", "it", published())

    assert match == second.match


@pytest.mark.django_db
def test_the_cascade_finds_nothing_when_no_matcher_does(certificate):
    cascade = CascadeMatcher(StubMatcher(None), StubMatcher(None))

    assert cascade.best_match("?", "it", published()) is None


# --- through find_best_match and the questions API ---------------------------


@pytest.mark.postgres
@pytest.mark.django_db
def test_full_text_answers_first(certificate):
    match = find_best_match(
        "Come richiedo il certificato di iscrizione?",
        office_code=OfficeCode.ADMIN_OFFICE,
        language="it",
    )

    assert match is not None
    assert match.faq == certificate
    assert match.matched_by == MatchMethod.FULL_TEXT


@pytest.mark.postgres
@pytest.mark.django_db
def test_semantic_search_answers_what_full_text_misses(certificate):
    question = "Mi serve un attestato: sono iscritto?"

    match = find_best_match(
        question, office_code=OfficeCode.ADMIN_OFFICE, language="it"
    )

    assert match is not None
    assert match.faq == certificate
    assert match.matched_by == MatchMethod.SEMANTIC


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_semantic_answer_looks_the_same_to_the_client(student_client, certificate):
    response = student_client.post(
        "/api/questions/",
        {
            "office": OfficeCode.ADMIN_OFFICE,
            "question": "Mi serve un attestato: sono iscritto?",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    match = response.json()["match"]
    assert set(match) == {"faq", "office", "score"}
    assert match["faq"]["id"] == certificate.id
    assert Inquiry.objects.get().matched_by == MatchMethod.SEMANTIC


@pytest.mark.django_db
def test_asking_records_how_the_answer_was_found(monkeypatch, certificate):
    monkeypatch.setattr(
        "faq.services.find_best_match",
        lambda *args: a_match(certificate, MatchMethod.SEMANTIC),
    )

    inquiry = ask_question(OfficeCode.ADMIN_OFFICE, "Un attestato?", "it")

    assert inquiry.matched_by == MatchMethod.SEMANTIC


@pytest.mark.django_db
def test_a_question_without_an_answer_records_no_method(monkeypatch):
    monkeypatch.setattr("faq.services.find_best_match", lambda *args: None)

    inquiry = ask_question(OfficeCode.ADMIN_OFFICE, "Dove si trova la mensa?", "it")

    assert inquiry.matched_by == ""
