"""Tests for matching a student's question with the published FAQs (FR7).

The matching is PostgreSQL full-text search, so nearly everything here is
marked `postgres`: on SQLite it would not be skipped for a good reason but fail
for a bad one. The one exception checks exactly that the service refuses to
run anywhere else.

The knowledge base below is small but written like the real one: questions
starting with "Come ...", answers that mention the same portals over and over.
That repetition is what the threshold has to see through.
"""

import pytest
from django.db import connection

from faq.matching import MatchingUnavailable, find_best_match
from faq.models import Faq
from pronto.enums import OfficeCode


def make_faq(office_code, question_it, answer_it, question_en="", answer_en=""):
    return Faq.objects.create(
        office_code=office_code,
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
        "Vorrei sapere come posso richiedere un certificato di iscrizione",
        office_code=OfficeCode.ADMIN_OFFICE,
        language="it",
    )

    assert match is not None
    assert match.faq == knowledge_base[0]
    assert match.office_code == OfficeCode.ADMIN_OFFICE
    assert match.score > 0


@pytest.mark.postgres
@pytest.mark.django_db
def test_italian_words_are_matched_by_their_stem(knowledge_base, certificate):
    # Plural against singular, and a verb in another person: "pagano" is not
    # "pago", but both are the stem "pag".
    assert (
        find_best_match("certificati iscrizioni", OfficeCode.ADMIN_OFFICE, "it").faq
        == certificate
    )
    assert (
        find_best_match("Quando si pagano le tasse?", OfficeCode.ADMIN_OFFICE, "it").faq
        == knowledge_base[1]
    )


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_question_made_only_of_stop_words_matches_nothing(knowledge_base):
    # Every FAQ starts with "Come": without the Italian stop words, this would
    # match all of them equally.
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
    # The student chose the wrong office: the answer is the internships
    # office's, and the match says so.
    match = find_best_match(
        "Come si attiva un tirocinio?", OfficeCode.ADMIN_OFFICE, "it"
    )

    assert match is not None
    assert match.faq == internship
    assert match.office_code == OfficeCode.INTERNSHIPS


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_good_enough_match_in_the_office_wins_over_a_better_one_elsewhere(
    knowledge_base,
):
    # All three words are in the internship FAQ, only one in the tutor FAQ:
    # the office asked about still comes first, as long as its answer clears
    # the threshold.
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
def test_a_long_question_that_covers_a_faq_only_in_part_still_matches(
    knowledge_base, fees
):
    # Two of its eight meaningful words are about fees: the lower end of what
    # FAQ_MATCH_MIN_RANK has to let through.
    match = find_best_match(
        "Vorrei sapere se posso iscrivermi a un corso singolo pagando le tasse ridotte",
        OfficeCode.ADMIN_OFFICE,
        "it",
    )

    assert match is not None
    assert match.faq == fees


@pytest.mark.postgres
@pytest.mark.django_db
def test_one_incidental_word_in_an_answer_stays_under_the_default_threshold(
    knowledge_base,
):
    # "online" is in the answers of two FAQs, as the name of the portal. A
    # question that shares only that word with them is not about them, and
    # this is the overlap FAQ_MATCH_MIN_RANK is there to reject.
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
    # Runs on both databases: the vendor is faked, so the SQLite run and the
    # PostgreSQL run check the same thing. Returning "no match" here would be
    # indistinguishable from a knowledge base with no answer.
    monkeypatch.setattr(connection, "vendor", "sqlite")

    with pytest.raises(MatchingUnavailable):
        find_best_match("certificato", OfficeCode.ADMIN_OFFICE, "it")
