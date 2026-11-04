"""Tests for full-text FAQ matching (FR7), mostly marked `postgres`.

The FAQs below mimic the real ones: similar openings, the same portals.
"""

import pytest
from django.db import connection

from faq.matching import MatchingUnavailable, find_best_match
from faq.models import Faq
from pronto.enums import OfficeCode
from tests.conftest import office_for


def make_faq(office_code, question_it, answer_it, question_en="", answer_en=""):
    return Faq.objects.create(
        office=office_for(office_code),
        question_it=question_it,
        answer_it=answer_it,
        question_en=question_en or question_it,
        answer_en=answer_en or answer_it,
    )


@pytest.fixture
def certificate(db):
    return make_faq(
        OfficeCode.ADMIN_OFFICE,
        "Come richiedo un certificato di iscrizione?",
        "Dal portale Studenti Online, sezione Certificati, puoi scaricarlo subito.",
        "How do I request a certificate of enrolment?",
        "From the Studenti Online portal, Certificates section, you can download it at once.",
    )


@pytest.fixture
def fees(db):
    return make_faq(
        OfficeCode.ADMIN_OFFICE,
        "Come pago le tasse universitarie?",
        "Le tasse si pagano con PagoPA dal portale Studenti Online.",
        "How do I pay my university fees?",
        "Fees are paid with PagoPA from the Studenti Online portal.",
    )


@pytest.fixture
def internship(db):
    return make_faq(
        OfficeCode.INTERNSHIPS,
        "Come attivo un tirocinio curriculare?",
        "Compilando il progetto formativo su AlmaLaurea insieme al tutor.",
        "How do I start a curricular internship?",
        "By filling in the training project on AlmaLaurea with your tutor.",
    )


@pytest.fixture
def knowledge_base(certificate, fees, internship):
    return [certificate, fees, internship]


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_question_is_matched_with_the_best_faq_of_its_office(knowledge_base):
    match = find_best_match(
        "Come richiedere un certificato di iscrizione?",
        office_code=OfficeCode.ADMIN_OFFICE,
        language="it",
    )

    assert match is not None
    assert match.faq == knowledge_base[0]
    assert match.office_code == OfficeCode.ADMIN_OFFICE
    assert match.score > 0


@pytest.mark.postgres
@pytest.mark.django_db
def test_without_an_office_every_office_is_searched(knowledge_base, internship):
    match = find_best_match(
        "Come attivo un tirocinio curriculare?", office_code=None, language="it"
    )

    assert match is not None
    assert match.faq == internship
    assert match.office_code == OfficeCode.INTERNSHIPS


@pytest.mark.postgres
@pytest.mark.django_db
def test_italian_words_are_matched_by_their_stem(knowledge_base, certificate):
    # Plural and singular share the stem "pag".
    assert (
        find_best_match("certificati iscrizioni", OfficeCode.ADMIN_OFFICE, "it").faq
        == certificate
    )
    assert (
        find_best_match(
            "Come si pagano le tasse universitarie?", OfficeCode.ADMIN_OFFICE, "it"
        ).faq
        == knowledge_base[1]
    )


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_question_made_only_of_stop_words_matches_nothing(knowledge_base):
    # Every FAQ starts with "Come", an Italian stop word.
    assert find_best_match("Come e dove?", OfficeCode.ADMIN_OFFICE, "it") is None


@pytest.mark.postgres
@pytest.mark.django_db
def test_an_english_question_is_searched_with_english_stemming(knowledge_base, fees):
    match = find_best_match("Paying the fees", OfficeCode.ADMIN_OFFICE, "en")

    assert match is not None
    assert match.faq == fees


@pytest.mark.postgres
@pytest.mark.django_db
def test_the_language_picks_the_columns_that_are_searched(knowledge_base):
    # "enrolment" only occurs in the English text of the certificate FAQ.
    assert find_best_match("enrolment", OfficeCode.ADMIN_OFFICE, "it") is None
    assert find_best_match("enrolment", OfficeCode.ADMIN_OFFICE, "en") is not None


@pytest.mark.postgres
@pytest.mark.django_db
def test_an_unpublished_faq_is_never_suggested(certificate):
    certificate.is_active = False
    certificate.save()

    assert (
        find_best_match("certificato di iscrizione", OfficeCode.ADMIN_OFFICE, "it")
        is None
    )


@pytest.mark.postgres
@pytest.mark.django_db
def test_without_a_match_in_the_office_every_office_is_searched(
    knowledge_base, internship
):
    # Wrong office chosen: the match is the internships office's FAQ.
    match = find_best_match(
        "Come si attiva un tirocinio?", OfficeCode.ADMIN_OFFICE, "it"
    )

    assert match is not None
    assert match.faq == internship
    assert match.office_code == OfficeCode.INTERNSHIPS


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_good_enough_match_in_the_office_wins_over_a_better_one_elsewhere(
    settings, knowledge_base
):
    # The chosen office comes first if its FAQ clears the (low) threshold here.
    settings.FAQ_MATCH_MIN_RANK = 0.1
    tutor = make_faq(
        OfficeCode.ADMIN_OFFICE,
        "Chi è il mio tutor accademico?",
        "Lo trovi nella pagina del corso.",
    )

    match = find_best_match(
        "tutor tirocinio curriculare", OfficeCode.ADMIN_OFFICE, "it"
    )

    assert match is not None
    assert match.faq == tutor


@pytest.mark.postgres
@pytest.mark.django_db
def test_an_unrelated_question_has_no_match(knowledge_base):
    assert (
        find_best_match(
            "Dove posso parcheggiare la bicicletta?", OfficeCode.ADMIN_OFFICE, "it"
        )
        is None
    )


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_long_question_that_covers_a_faq_only_in_part_is_left_to_semantic_search(
    knowledge_base,
):
    # Rank 0.15 is below FAQ_MATCH_MIN_RANK, and semantic search is off.
    match = find_best_match(
        "Vorrei sapere se posso iscrivermi a un corso singolo pagando le tasse ridotte",
        OfficeCode.ADMIN_OFFICE,
        "it",
    )

    assert match is None


@pytest.mark.postgres
@pytest.mark.django_db
def test_one_incidental_word_in_an_answer_stays_under_the_default_threshold(
    knowledge_base,
):
    # Sharing only the portal name "online" is not enough.
    assert (
        find_best_match(
            "Vorrei sapere se la mensa del campus ha un menù online",
            OfficeCode.ADMIN_OFFICE,
            "it",
        )
        is None
    )


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_score_equal_to_the_threshold_is_a_match(settings, certificate):
    settings.FAQ_MATCH_MIN_RANK = 0.000001
    question = "certificato di iscrizione"
    score = find_best_match(question, OfficeCode.ADMIN_OFFICE, "it").score

    settings.FAQ_MATCH_MIN_RANK = score
    assert find_best_match(question, OfficeCode.ADMIN_OFFICE, "it") is not None

    settings.FAQ_MATCH_MIN_RANK = score + 0.000001
    assert find_best_match(question, OfficeCode.ADMIN_OFFICE, "it") is None


@pytest.mark.django_db
def test_matching_refuses_to_run_without_postgres(monkeypatch, certificate):
    # The vendor is faked, so this runs on both databases.
    monkeypatch.setattr(connection, "vendor", "sqlite")

    with pytest.raises(MatchingUnavailable):
        find_best_match("certificato", OfficeCode.ADMIN_OFFICE, "it")
