"""Tests for the anonymisation applied to FAQs before they are imported (NFR4).

Every name, address and number below is invented. The real helpdesk data
never appears in the tests.
"""

import pytest

from faq.anonymisation import anonymise


# --- e-mail addresses --------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "mario.rossi@studio.unibo.it",
        "mario.rossi98@gmail.com",
        "M.Rossi+helpdesk@Example.ORG",
    ],
)
def test_a_personal_email_address_is_replaced(address):
    assert anonymise(f"Scrivo da {address}, grazie") == "Scrivo da [EMAIL], grazie"


def test_an_institutional_office_mailbox_is_kept():
    # Students have @studio.unibo.it addresses, so an @unibo.it one belongs to
    # the university: the office to write to, which is what the answer is for.
    text = "Scrivi a segreteria.cesena@unibo.it per il certificato."

    assert anonymise(text) == text


def test_a_subdomain_of_the_institutional_domain_is_not_kept():
    assert anonymise("x@fake.unibo.it") == "[EMAIL]"


# --- student ID numbers ------------------------------------------------------


def test_a_unibo_matricola_is_replaced_even_without_a_cue():
    assert anonymise("Il mio numero è 0000912345.") == "Il mio numero è [STUDENT_ID]."


@pytest.mark.parametrize(
    "text",
    [
        "matricola 912345",
        "Matricola: 0000912345",
        "matr. 1234567",
        "n. matricola 88123",
        "my student ID is 912345",
        "student number: 912345",
    ],
)
def test_a_number_introduced_as_a_student_id_is_replaced(text):
    assert "[STUDENT_ID]" in anonymise(text)
    assert not any(ch.isdigit() for ch in anonymise(text))


# --- phone numbers -----------------------------------------------------------


@pytest.mark.parametrize(
    "number",
    [
        "3331234567",
        "333 1234567",
        "333 123 4567",
        "333-123-4567",
        "333.123.4567",
        "+39 333 1234567",
        "+393331234567",
        "0039 333 1234567",
        "0547 123456",
        "0547123456",
        "051 2091234",
        "+39 051 209 1234",
        "+44 20 7946 0958",
    ],
)
def test_a_phone_number_is_replaced(number):
    assert anonymise(f"chiamami al {number} dopo le 18") == (
        "chiamami al [PHONE] dopo le 18"
    )


# --- tax codes ---------------------------------------------------------------


def test_an_italian_tax_code_is_replaced():
    assert anonymise("CF RSSMRA98A01C573X") == "CF [TAX_CODE]"


# --- names -------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Ho parlato con il Prof. Rossi", "Ho parlato con il Prof. [NAME]"),
        ("dalla prof.ssa Anna Bianchi", "dalla prof.ssa [NAME]"),
        ("la Dott.ssa Maria De Luca", "la Dott.ssa [NAME]"),
        ("il dott. Verdi mi ha detto", "il dott. [NAME] mi ha detto"),
        ("Sig.ra Neri", "Sig.ra [NAME]"),
        ("I wrote to Professor Smith", "I wrote to Professor [NAME]"),
        ("Dear Mr. John Smith", "Dear Mr. [NAME]"),
    ],
)
def test_a_name_after_an_honorific_is_replaced(text, expected):
    assert anonymise(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "Buongiorno, mi chiamo Luca e vorrei",
            "Buongiorno, mi chiamo [NAME] e vorrei",
        ),
        ("Il mio nome è Giulia Neri.", "Il mio nome è [NAME]."),
        ("Hi, my name is John Smith and", "Hi, my name is [NAME] and"),
        ("Salve, sono Mario Rossi, studente", "Salve, sono [NAME], studente"),
        ("Hello, I am John Smith from Spain", "Hello, I am [NAME] from Spain"),
        ("I'm Jane Doe", "I'm [NAME]"),
    ],
)
def test_a_name_after_a_self_introduction_is_replaced(text, expected):
    assert anonymise(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Come faccio? Grazie, Mario Rossi", "Come faccio? Grazie, [NAME]"),
        (
            "Come faccio?\nCordiali saluti\nAnna",
            "Come faccio?\nCordiali saluti\n[NAME]",
        ),
        (
            "How do I apply? Best regards, John Smith.",
            "How do I apply? Best regards, [NAME].",
        ),
        ("Can you help? Thanks, Jane", "Can you help? Thanks, [NAME]"),
    ],
)
def test_a_name_signing_off_the_text_is_replaced(text, expected):
    assert anonymise(text) == expected


# --- no false positives ------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Il bando 2024/2025 scade il 15/03/2025 alle 12:00.",
        "La scadenza è il 03.12.2024, la tassa è di 1.500 euro.",
        "Servono 180 CFU e un ISEE sotto i 23000 euro.",
        "L'aula 3.4 apre alle 9:30, ingresso 2.",
        "Nel 2023 ero iscritto al primo anno.",
        "Sono iscritta a Ingegneria Biomedica, sono laureata in Scienze Informatiche.",
        "I am enrolled in Computer Engineering.",
        "Qual è la differenza tra Ing. Biomedica e Ing. Meccanica?",
        "Il Campus di Cesena è aperto? Grazie mille",
        "Il Professore di Analisi riceve il lunedì.",
        "Vedi https://corsi.unibo.it/laurea/esempio/1234567890 per i dettagli.",
        "Sono aperte le iscrizioni? Sono uno studente Erasmus.",
    ],
)
def test_ordinary_text_is_left_untouched(text):
    assert anonymise(text) == text


def test_several_kinds_of_personal_data_are_replaced_in_one_text():
    text = (
        "Buongiorno, sono Mario Rossi (matricola 0000912345), "
        "mio numero 333 1234567, mail mario.rossi@studio.unibo.it. Grazie, Mario"
    )

    assert anonymise(text) == (
        "Buongiorno, sono [NAME] (matricola [STUDENT_ID]), "
        "mio numero [PHONE], mail [EMAIL]. Grazie, [NAME]"
    )


def test_anonymising_twice_changes_nothing_more():
    # The importer's natural key is the anonymised question: it must be stable.
    once = anonymise("Salve, sono Mario Rossi, 333 1234567")

    assert anonymise(once) == once


def test_empty_text_stays_empty():
    assert anonymise("") == ""
