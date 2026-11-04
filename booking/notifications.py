"""Appointment e-mails (FR13-FR15), sent after the transaction commits.

A failed e-mail is logged, not raised. Students get their question's
language, employees Italian. Templates are in
``booking/templates/booking/email/``: first line subject, then body.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Weekday

logger = logging.getLogger(__name__)

EMPLOYEE_LANG = "it"

WEEKDAYS = {
    "it": Weekday.labels,
    "en": [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ],
}
MONTHS = {
    "it": [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ],
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
}


def appointment_booked(appointment):
    """Confirm the booking to the student (FR13) and tell the employee (FR14)."""
    _on_commit(
        appointment, "booked_student", appointment.student, appointment.question_lang
    )
    _on_commit(appointment, "booked_employee", appointment.employee.user, EMPLOYEE_LANG)


def appointment_cancelled(appointment, by):
    """Tell whoever did not cancel (FR15); both, if an admin cancelled."""
    if by != appointment.student:
        _on_commit(
            appointment,
            "cancelled_student",
            appointment.student,
            appointment.question_lang,
        )
    if by != appointment.employee.user:
        _on_commit(
            appointment, "cancelled_employee", appointment.employee.user, EMPLOYEE_LANG
        )


def when(slot, lang):
    """`slot` in local time, e.g. "lunedì 5 ottobre 2026, 10:00".

    By hand, because the OS may lack the Italian locale.
    """
    local = timezone.localtime(slot)
    weekday = WEEKDAYS[lang][local.weekday()]
    month = MONTHS[lang][local.month - 1]
    return f"{weekday} {local.day} {month} {local.year}, {local:%H:%M}"


def _on_commit(appointment, template, recipient, lang):
    subject, body = _render(appointment, template, lang)
    transaction.on_commit(lambda: _send(subject, body, recipient.email))


def _render(appointment, template, lang):
    context = {
        "appointment": appointment,
        "office": getattr(appointment.office, f"name_{lang}"),
        "when": when(appointment.slot, lang),
        "student": appointment.student,
        "faq": appointment.suggested_faq,
    }
    text = render_to_string(f"booking/email/{template}.{lang}.txt", context)
    subject, _, body = text.strip().partition("\n")
    return subject.strip(), body.strip() + "\n"


def _send(subject, body, address):
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[address],
        )
    except Exception:
        # Any failure: the booking stands anyway.
        logger.exception("Could not send %r to %s", subject, address)
