"""Enumerations shared across the project's apps.

Value objects only: no models and no app of their own, so `accounts`, `booking`
and `faq` can all depend on them without depending on each other.
"""

from django.db import models


class OfficeCode(models.TextChoices):
    """The helpdesk offices a student can book an appointment with."""

    GUIDANCE = "GUIDANCE", "Orientamento"
    ADMIN_OFFICE = "ADMIN_OFFICE", "Segreteria studenti"
    INTERNATIONAL = "INTERNATIONAL", "Relazioni internazionali"
    INTERNSHIPS = "INTERNSHIPS", "Tirocini"


class Role(models.TextChoices):
    """What a user is allowed to do, derived from their institutional email."""

    STUDENT = "STUDENT", "Studente"
    EMPLOYEE = "EMPLOYEE", "Dipendente"
    ADMIN = "ADMIN", "Amministratore"


class AppointmentStatus(models.TextChoices):
    """The life cycle of an appointment."""

    BOOKED = "BOOKED", "Prenotato"
    CANCELLED = "CANCELLED", "Annullato"
    COMPLETED = "COMPLETED", "Completato"
