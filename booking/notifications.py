"""The e-mails an appointment's life cycle sends (FR13-FR15).

Each function is called by `booking.services` from inside the transaction that
changes the appointment, and only *registers* the e-mails: they are sent once
that transaction commits. A booking rolled back therefore tells nobody, and a
slow or failing mail server never holds a database transaction open.

Delivery is best-effort. A failed e-mail is logged, never raised: by the time
it is sent the booking is already committed, and the student is better served
by a booking without its confirmation than by an error for a booking that
exists. Each e-mail is sent on its own, so one bounced address does not stop
the other person from hearing about it.

Students are written to in the language they asked their question in;
employees always in Italian. The texts live in
``booking/templates/booking/email/``: the first line of each file is the
subject, the rest is the body.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

EMPLOYEE_LANG = "it"

WEEKDAYS = {
    "it": [
        "lunedì",
        "martedì",
        "mercoledì",
        "giovedì",
        "venerdì",
        "sabato",
        "domenica",
    ],
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
    """Tell whoever did not cancel (FR15).

    The person who cancelled already knows. When someone else — an admin —
    cancels, both the student and the employee are told.
    """
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
    """`slot` in the helpdesk's local time, spelled out: "lunedì 5 ottobre 2026, 10:00".

    Written by hand rather than through the OS locale, which may not have
    Italian installed and would then fall back to English without a word.
    """
    local = timezone.localtime(slot)
    weekday = WEEKDAYS[lang][local.weekday()]
    month = MONTHS[lang][local.month - 1]
    return f"{weekday} {local.day} {month} {local.year}, {local:%H:%M}"


def _on_commit(appointment, template, recipient, lang):
    # Rendered now, while the appointment is as this transaction left it;
    # only the sending waits for the commit.
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
        # Broad on purpose: SMTP errors, DNS failures and timeouts all mean the
        # same thing here — the e-mail did not go, and the booking stands.
        logger.exception("Could not send %r to %s", subject, address)
