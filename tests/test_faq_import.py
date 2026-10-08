"""Tests for the ``import_faqs`` management command.

Each test writes a small workbook of invented rows to ``tmp_path``, laid out
like the helpdesk export: ``Ufficio | Office | Domanda | Question | Risposta``,
plus ``Answer`` in the tests about the English answer.
"""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from openpyxl import Workbook

from faq.management.commands import import_faqs
from faq.models import Faq
from offices.models import Office
from pronto.enums import OfficeCode

HEADER = ("Ufficio", "Office", "Domanda", "Question", "Risposta")
BILINGUAL_HEADER = (*HEADER, "Answer")

ENROLMENT = (
    "Segreteria",
    "Student Administration Office",
    "Come mi iscrivo?",
    "How do I enrol?",
    "Da Studenti Online.",
)
ERASMUS = (
    "Relazioni Internazionali",
    "International Relations",
    "Quando esce il bando Erasmus?",
    "When is the Erasmus call published?",
    "A febbraio.",
)


def write_workbook(path, *rows, header=HEADER):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Centralino"
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    return path


def run(path, *args):
    """Run the command and return what it printed."""
    out = StringIO()
    call_command("import_faqs", str(path), *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def workbook(tmp_path):
    return write_workbook(tmp_path / "faqs.xlsx", ENROLMENT, ERASMUS)


# --- creating ----------------------------------------------------------------


@pytest.mark.django_db
def test_each_answered_row_becomes_a_faq(workbook):
    run(workbook)

    stored = Faq.objects.get(question_it="Come mi iscrivo?")
    assert stored.office.code == OfficeCode.ADMIN_OFFICE
    assert stored.question_en == "How do I enrol?"
    assert stored.answer_it == "Da Studenti Online."
    assert Faq.objects.count() == 2


@pytest.mark.parametrize(
    "ufficio, office, code",
    [
        ("Orientamento", "Guidance and Admissions", OfficeCode.GUIDANCE),
        ("Segreteria", "Student Administration Office", OfficeCode.ADMIN_OFFICE),
        (
            "Relazioni Internazionali",
            "International Relations",
            OfficeCode.INTERNATIONAL,
        ),
        ("Tirocini", "Internships", OfficeCode.INTERNSHIPS),
        (" tirocini ", None, OfficeCode.INTERNSHIPS),
        (None, "Internships", OfficeCode.INTERNSHIPS),
        ("Segreteria studenti", None, OfficeCode.ADMIN_OFFICE),
        ("INTERNATIONAL", None, OfficeCode.INTERNATIONAL),
    ],
)
@pytest.mark.django_db
def test_the_office_is_read_from_either_office_column(tmp_path, ufficio, office, code):
    path = write_workbook(
        tmp_path / "f.xlsx", (ufficio, office, "Domanda?", "Q?", "R.")
    )

    run(path)

    assert Faq.objects.get().office.code == code


@pytest.mark.django_db
def test_an_office_not_in_the_database_yet_is_created_as_seed_offices_would(
    workbook,
):
    output = run(workbook)

    admin_office = Office.objects.get(code=OfficeCode.ADMIN_OFFICE)
    assert admin_office.name_it == "Segreteria studenti"
    assert admin_office.name_en == "Student Administration Office"
    assert admin_office.contact_email == "segreteria@unibo.it"
    assert admin_office.is_active
    assert "Offices created: ADMIN_OFFICE, INTERNATIONAL" in output


@pytest.mark.django_db
def test_an_office_already_in_the_database_is_used_as_it_is(other_office, workbook):
    """`other_office` is the Student Administration Office, with its own names."""
    output = run(workbook)

    assert Faq.objects.get(question_it="Come mi iscrivo?").office == other_office
    other_office.refresh_from_db()
    assert other_office.name_en == "Student office"
    assert "Offices created: INTERNATIONAL" in output


@pytest.mark.django_db
def test_the_italian_answer_stands_in_for_the_missing_english_one(workbook):
    # The sheet has no English answer; an empty one would show English
    # readers nothing at all, the Italian text at least answers them.
    run(workbook)

    stored = Faq.objects.get(question_it="Come mi iscrivo?")
    assert stored.answer_en == stored.answer_it


@pytest.mark.django_db
def test_the_english_answer_is_read_from_the_sheet(tmp_path):
    path = write_workbook(
        tmp_path / "f.xlsx",
        (*ENROLMENT, "From Studenti Online."),
        header=BILINGUAL_HEADER,
    )

    run(path)

    stored = Faq.objects.get()
    assert stored.answer_it == "Da Studenti Online."
    assert stored.answer_en == "From Studenti Online."


@pytest.mark.django_db
def test_the_italian_answer_stands_in_for_an_empty_english_cell(tmp_path):
    path = write_workbook(
        tmp_path / "f.xlsx",
        (*ENROLMENT, None),
        (*ERASMUS, "In February."),
        header=BILINGUAL_HEADER,
    )

    run(path)

    assert Faq.objects.get(question_it="Come mi iscrivo?").answer_en == (
        "Da Studenti Online."
    )
    assert Faq.objects.get(question_it="Quando esce il bando Erasmus?").answer_en == (
        "In February."
    )


@pytest.mark.django_db
def test_the_english_answer_is_anonymised(tmp_path):
    path = write_workbook(
        tmp_path / "f.xlsx",
        (*ENROLMENT, "Call 333 1234567 or write to mario.rossi@studio.unibo.it."),
        header=BILINGUAL_HEADER,
    )

    run(path)

    assert Faq.objects.get().answer_en == "Call [PHONE] or write to [EMAIL]."


@pytest.mark.django_db
def test_the_italian_question_stands_in_for_a_missing_english_one(tmp_path):
    path = write_workbook(
        tmp_path / "f.xlsx", ("Tirocini", "Internships", "Domanda?", None, "R.")
    )

    run(path)

    assert Faq.objects.get().question_en == "Domanda?"


@pytest.mark.django_db
def test_a_long_question_is_imported_whole(tmp_path):
    # The real export has a question of 308 characters: context first, then
    # the question itself.
    question = "Sono uno studente iscritto al secondo anno. " * 7 + "Come faccio?"
    path = write_workbook(
        tmp_path / "f.xlsx", ("Tirocini", "Internships", question, None, "R.")
    )

    output = run(path)

    assert "Created: 1" in output
    assert Faq.objects.get().question_it == question
    assert len(question) > 255


@pytest.mark.django_db
def test_imported_faqs_are_unpublished_until_someone_reviews_them(workbook):
    run(workbook)

    assert not Faq.objects.filter(is_active=True).exists()


@pytest.mark.django_db
def test_imported_faqs_can_be_published_straight_away(workbook):
    run(workbook, "--publish")

    assert Faq.objects.filter(is_active=True).count() == 2


@pytest.mark.django_db
def test_questions_and_answers_are_anonymised_in_both_languages(tmp_path):
    path = write_workbook(
        tmp_path / "f.xlsx",
        (
            "Segreteria",
            "Student Administration Office",
            "Sono Mario Rossi, matricola 0000912345: come mi iscrivo?",
            "I am Mario Rossi, how do I enrol? mario.rossi@studio.unibo.it",
            "Richiamare il 333 1234567.",
        ),
    )

    run(path)

    stored = Faq.objects.get()
    assert stored.question_it == "Sono [NAME], matricola [STUDENT_ID]: come mi iscrivo?"
    assert stored.question_en == "I am [NAME], how do I enrol? [EMAIL]"
    assert stored.answer_it == "Richiamare il [PHONE]."
    assert stored.answer_en == "Richiamare il [PHONE]."


@pytest.mark.django_db
def test_the_summary_counts_what_was_created(workbook):
    output = run(workbook)

    assert "Created: 2" in output
    assert "Updated: 0" in output
    assert "Skipped: 0" in output


# --- running again -----------------------------------------------------------


@pytest.mark.django_db
def test_running_the_import_twice_creates_nothing_the_second_time(workbook):
    run(workbook)

    output = run(workbook)

    assert Faq.objects.count() == 2
    assert "Created: 0" in output
    assert "Unchanged: 2" in output


@pytest.mark.django_db
def test_a_changed_answer_updates_the_existing_faq(tmp_path, workbook):
    run(workbook)
    changed = (*ENROLMENT[:4], "Da Studenti Online, entro settembre.")

    output = run(write_workbook(tmp_path / "v2.xlsx", changed, ERASMUS))

    stored = Faq.objects.get(question_it="Come mi iscrivo?")
    assert stored.answer_it == "Da Studenti Online, entro settembre."
    assert stored.answer_en == "Da Studenti Online, entro settembre."
    assert Faq.objects.count() == 2
    assert "Updated: 1" in output
    assert "Unchanged: 1" in output


@pytest.mark.django_db
def test_a_changed_english_question_updates_the_existing_faq(tmp_path, workbook):
    run(workbook)
    changed = (*ENROLMENT[:3], "How can I enrol?", ENROLMENT[4])

    run(write_workbook(tmp_path / "v2.xlsx", changed))

    assert (
        Faq.objects.get(question_it="Come mi iscrivo?").question_en
        == "How can I enrol?"
    )


@pytest.mark.django_db
def test_running_again_keeps_an_english_answer_written_in_the_admin(tmp_path, workbook):
    run(workbook)
    Faq.objects.filter(question_it="Come mi iscrivo?").update(
        answer_en="From Studenti Online."
    )
    changed = (*ENROLMENT[:4], "Da Studenti Online, entro settembre.")

    run(write_workbook(tmp_path / "v2.xlsx", changed))

    stored = Faq.objects.get(question_it="Come mi iscrivo?")
    assert stored.answer_it == "Da Studenti Online, entro settembre."
    assert stored.answer_en == "From Studenti Online."


@pytest.mark.django_db
def test_running_again_keeps_it_when_the_english_cell_is_empty(tmp_path, workbook):
    run(workbook)
    Faq.objects.filter(question_it="Come mi iscrivo?").update(
        answer_en="From Studenti Online."
    )

    run(
        write_workbook(
            tmp_path / "v2.xlsx", (*ENROLMENT, None), header=BILINGUAL_HEADER
        )
    )

    assert (
        Faq.objects.get(question_it="Come mi iscrivo?").answer_en
        == "From Studenti Online."
    )


@pytest.mark.django_db
def test_a_changed_english_answer_updates_the_existing_faq(tmp_path):
    original = (*ENROLMENT, "From Studenti Online.")
    run(write_workbook(tmp_path / "v1.xlsx", original, header=BILINGUAL_HEADER))
    changed = (*ENROLMENT, "From Studenti Online, by September.")

    output = run(write_workbook(tmp_path / "v2.xlsx", changed, header=BILINGUAL_HEADER))

    stored = Faq.objects.get()
    assert stored.answer_en == "From Studenti Online, by September."
    assert "Updated: 1" in output


@pytest.mark.django_db
def test_the_english_answer_in_the_sheet_replaces_the_one_in_the_admin(
    tmp_path, workbook
):
    # The sheet is the source of truth for both answers, as it already is for
    # the Italian one: an edit made in the admin lasts until the next import.
    run(workbook)
    Faq.objects.filter(question_it="Come mi iscrivo?").update(
        answer_en="Written in the admin."
    )

    run(
        write_workbook(
            tmp_path / "v2.xlsx",
            (*ENROLMENT, "From Studenti Online."),
            header=BILINGUAL_HEADER,
        )
    )

    assert (
        Faq.objects.get(question_it="Come mi iscrivo?").answer_en
        == "From Studenti Online."
    )


@pytest.mark.django_db
def test_running_again_keeps_the_publication_decided_in_the_admin(workbook):
    run(workbook)
    Faq.objects.filter(question_it="Come mi iscrivo?").update(is_active=True)

    run(workbook)

    assert Faq.objects.get(question_it="Come mi iscrivo?").is_active


# --- skipping ----------------------------------------------------------------


@pytest.mark.django_db
def test_unusable_rows_are_skipped_and_counted_by_reason(tmp_path):
    path = write_workbook(
        tmp_path / "f.xlsx",
        ENROLMENT,
        ("Mensa", "Canteen", "A che ora apre?", "When does it open?", "Alle 12."),
        ("Tirocini", "Internships", "Come trovo un tirocinio?", "How?", None),
        ("Tirocini", "Internships", "Come trovo un'azienda?", "How?", "   "),
        ("Tirocini", "Internships", None, None, "Risposta senza domanda."),
        (None, None, None, None, None),
    )

    output = run(path)

    assert Faq.objects.count() == 1
    assert "Created: 1" in output
    assert "Skipped: 5" in output
    assert "unknown office: 1" in output
    assert "no answer: 2" in output
    assert "no question: 1" in output
    assert "empty row: 1" in output


# --- failing -----------------------------------------------------------------


def test_a_missing_file_is_reported(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        run(tmp_path / "missing.xlsx")


def test_a_sheet_without_the_expected_columns_is_refused(tmp_path):
    path = write_workbook(tmp_path / "f.xlsx", header=("Ufficio", "Domanda"))

    with pytest.raises(CommandError, match="Risposta"):
        run(path)


@pytest.mark.django_db
def test_a_failure_halfway_leaves_the_database_as_it_was(tmp_path, monkeypatch):
    path = write_workbook(tmp_path / "f.xlsx", ENROLMENT, ERASMUS)
    anonymised = []

    def anonymise_then_fail(text):
        anonymised.append(text)
        if len(anonymised) > 4:  # the second row
            raise RuntimeError("boom")
        return text

    monkeypatch.setattr(import_faqs, "anonymise", anonymise_then_fail)

    with pytest.raises(RuntimeError):
        run(path)

    assert not Faq.objects.exists()


def test_a_file_that_is_not_a_workbook_is_refused(tmp_path):
    path = tmp_path / "faqs.xlsx"
    path.write_text("Ufficio;Domanda;Risposta\n")

    with pytest.raises(CommandError, match="Not an .xlsx workbook"):
        run(path)


def test_an_unknown_sheet_is_reported(workbook):
    with pytest.raises(CommandError, match="No sheet named"):
        run(workbook, "--sheet", "Missing")


@pytest.mark.django_db
def test_a_sheet_can_be_chosen_by_name(workbook):
    run(workbook, "--sheet", "Centralino")

    assert Faq.objects.count() == 2
