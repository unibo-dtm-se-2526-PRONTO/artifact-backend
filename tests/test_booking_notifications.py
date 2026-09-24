"""Tests for the e-mails a booking and a cancellation send (FR13-FR15).

The acceptance criterion is that each transition sends exactly one e-mail to
each person who has to hear about it, with enough context — office, date and
time, question — to act on it without opening the app.

E-mails go out on commit. Tests run inside a transaction that is never
committed, so `django_capture_on_commit_callbacks` stands in for the commit:
without it nothing would ever reach `mailoutbox`, and every "no e-mail" test
would pass for the wrong reason.
"""

import logging
from datetime import timedelta
from smtplib import SMTPException

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction

from booking import notifications
from booking.models import Appointment
from booking.services import (
    BookingError,
    book_appointment,
    cancel_appointment,
    complete_appointment,
)
from faq.models import Faq
from pronto.enums import AppointmentStatus, OfficeCode, Role
from tests.conftest import make_user, slot_at

User = get_user_model()

QUESTION = "Come faccio a cambiare il piano di studi?"


@pytest.fixture
def suggested(db):
    """The FAQ the student was shown and found unhelpful."""
    return Faq.objects.create(
        office_code=OfficeCode.GUIDANCE,
        question_it="Come si modifica il piano di studi?",
        question_en="How do I change my study plan?",
        answer_it="Il piano di studi si modifica da Studenti Online entro ottobre.",
        answer_en="The study plan is changed on Studenti Online by October.",
    )


@pytest.fixture
def admin(db):
    return make_user("admin@unibo.it", Role.ADMIN)


def book(student, office, day, lang="it", suggested_faq=None):
    return book_appointment(
        student=student,
        office=office,
        slot=slot_at(day, 10),
        question_text=QUESTION,
        question_lang=lang,
        suggested_faq=suggested_faq,
    )


def sent_to(mailoutbox, address):
    return [message for message in mailoutbox if message.to == [address]]


# --- booking (FR13, FR14) ----------------------------------------------------


@pytest.mark.django_db
def test_a_booking_emails_the_student_and_the_employee_once_each(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        book(student, office, day)

    assert len(mailoutbox) == 2
    assert len(sent_to(mailoutbox, student.email)) == 1
    assert len(sent_to(mailoutbox, employee.user.email)) == 1


@pytest.mark.django_db
def test_the_confirmation_carries_office_time_and_question(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        book(student, office, day)

    (message,) = sent_to(mailoutbox, student.email)
    assert "Orientamento" in message.body
    # `day` is always a Monday; 10:00 is the office's local time.
    assert "lunedì" in message.body
    assert "10:00" in message.body
    assert QUESTION in message.body


@pytest.mark.django_db
def test_the_confirmation_is_in_the_language_of_the_question(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        book(student, office, day, lang="en")

    (message,) = sent_to(mailoutbox, student.email)
    assert "Guidance" in message.body
    assert "Monday" in message.body
    assert "10:00" in message.body


@pytest.mark.django_db
def test_the_employee_is_written_to_in_italian_whatever_the_student_used(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        book(student, office, day, lang="en")

    (message,) = sent_to(mailoutbox, employee.user.email)
    assert "lunedì" in message.body
    assert "Orientamento" in message.body


@pytest.mark.django_db
def test_the_employee_sees_the_question_and_who_asked_it(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        book(student, office, day)

    (message,) = sent_to(mailoutbox, employee.user.email)
    assert student.email in message.body
    assert QUESTION in message.body
    assert "10:00" in message.body


@pytest.mark.django_db
def test_the_employee_sees_the_faq_that_did_not_help(
    office,
    employee,
    student,
    day,
    suggested,
    mailoutbox,
    django_capture_on_commit_callbacks,
):
    with django_capture_on_commit_callbacks(execute=True):
        book(student, office, day, suggested_faq=suggested)

    (message,) = sent_to(mailoutbox, employee.user.email)
    assert suggested.question_it in message.body
    assert suggested.answer_it in message.body


@pytest.mark.django_db
def test_without_a_faq_the_employee_is_told_none_was_found(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        book(student, office, day)

    (message,) = sent_to(mailoutbox, employee.user.email)
    assert "Nessuna FAQ" in message.body


@pytest.mark.django_db
def test_text_is_not_html_escaped(
    office, employee, day, mailoutbox, django_capture_on_commit_callbacks
):
    """The e-mails are plain text: an apostrophe stays an apostrophe."""
    student = make_user("dell.orto@studio.unibo.it", Role.STUDENT)
    with django_capture_on_commit_callbacks(execute=True):
        book_appointment(
            student=student,
            office=office,
            slot=slot_at(day, 10),
            question_text="Com'è l'esame d'inglese?",
            question_lang="it",
        )

    for message in mailoutbox:
        assert "Com'è l'esame d'inglese?" in message.body
        assert "&#x27;" not in message.body


@pytest.mark.django_db
def test_nothing_is_sent_for_a_booking_that_is_rolled_back(
    office, employee, student, day, django_capture_on_commit_callbacks
):
    """A booking undone by an enclosing transaction never happened, so nobody
    may be told about it."""
    with django_capture_on_commit_callbacks() as callbacks:
        with pytest.raises(RuntimeError), transaction.atomic():
            book(student, office, day)
            raise RuntimeError("the caller's own work failed")

    assert callbacks == []


@pytest.mark.django_db
def test_a_failed_email_does_not_undo_the_booking(
    office,
    employee,
    student,
    day,
    monkeypatch,
    caplog,
    django_capture_on_commit_callbacks,
):
    def smtp_is_down(*args, **kwargs):
        raise SMTPException("connection refused")

    monkeypatch.setattr(notifications, "send_mail", smtp_is_down)

    with caplog.at_level(logging.ERROR, logger="booking.notifications"):
        with django_capture_on_commit_callbacks(execute=True):
            appointment = book(student, office, day)

    assert Appointment.objects.filter(pk=appointment.pk).exists()
    assert "connection refused" in caplog.text


@pytest.mark.django_db
def test_one_failed_email_does_not_stop_the_other(
    office,
    employee,
    student,
    day,
    monkeypatch,
    mailoutbox,
    django_capture_on_commit_callbacks,
):
    """The employee still hears about the booking if the student's address
    bounces, and the other way round."""
    real_send_mail = notifications.send_mail

    def refuse_the_student(*args, recipient_list, **kwargs):
        if recipient_list == [student.email]:
            raise SMTPException("mailbox unavailable")
        return real_send_mail(*args, recipient_list=recipient_list, **kwargs)

    monkeypatch.setattr(notifications, "send_mail", refuse_the_student)

    with django_capture_on_commit_callbacks(execute=True):
        book(student, office, day)

    assert [message.to for message in mailoutbox] == [[employee.user.email]]


# --- cancelling (FR15) -------------------------------------------------------


@pytest.mark.django_db
def test_a_student_cancelling_tells_the_employee_only(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    appointment = book(student, office, day)

    with django_capture_on_commit_callbacks(execute=True):
        cancel_appointment(appointment, by=student)

    (message,) = mailoutbox
    assert message.to == [employee.user.email]
    assert "10:00" in message.body
    assert QUESTION in message.body


@pytest.mark.django_db
def test_an_employee_cancelling_tells_the_student_only(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    appointment = book(student, office, day, lang="en")

    with django_capture_on_commit_callbacks(execute=True):
        cancel_appointment(appointment, by=employee.user)

    (message,) = mailoutbox
    assert message.to == [student.email]
    assert "Guidance" in message.body
    assert "Monday" in message.body
    assert "10:00" in message.body


@pytest.mark.django_db
def test_an_admin_cancelling_tells_both(
    office,
    employee,
    student,
    admin,
    day,
    mailoutbox,
    django_capture_on_commit_callbacks,
):
    appointment = book(student, office, day)

    with django_capture_on_commit_callbacks(execute=True):
        cancel_appointment(appointment, by=admin)

    assert sorted(message.to[0] for message in mailoutbox) == sorted(
        [student.email, employee.user.email]
    )


@pytest.mark.django_db
def test_a_refused_cancellation_sends_nothing(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    appointment = book(student, office, day)
    cancel_appointment(appointment, by=student)

    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(BookingError):
            cancel_appointment(appointment, by=student)

    assert mailoutbox == []


# --- completing --------------------------------------------------------------


@pytest.mark.django_db
def test_completing_sends_nothing(
    office, employee, student, day, mailoutbox, django_capture_on_commit_callbacks
):
    appointment = book(student, office, day)
    # Rewound through a queryset, as the appointment API tests do: a meeting
    # has to be over before it can be completed.
    Appointment.objects.filter(pk=appointment.pk).update(
        slot=appointment.slot - timedelta(days=7)
    )
    appointment.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        complete_appointment(appointment)

    assert appointment.status == AppointmentStatus.COMPLETED
    assert mailoutbox == []
