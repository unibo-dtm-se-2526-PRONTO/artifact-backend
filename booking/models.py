from django.conf import settings
from django.db import models
from django.db.models import Q

from pronto.enums import AppointmentStatus, OfficeCode


class Office(models.Model):
    """A helpdesk office students can book an appointment with.

    ``code`` is the stable identifier shared with the `faq` app and the
    frontend; the display names are stored per language so the API can answer
    in the language the student asked in.
    """

    code = models.CharField(
        max_length=32,
        unique=True,
        choices=OfficeCode.choices,
        verbose_name="codice ufficio",
    )
    name_it = models.CharField(max_length=128, verbose_name="nome (italiano)")
    name_en = models.CharField(max_length=128, verbose_name="nome (inglese)")
    contact_email = models.EmailField(verbose_name="email di contatto")
    slot_duration_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name="durata dello slot (minuti)",
        help_text="Lunghezza di un appuntamento presso questo ufficio.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="attivo",
        help_text="Gli uffici non attivi non accettano nuove prenotazioni.",
    )

    class Meta:
        verbose_name = "ufficio"
        verbose_name_plural = "uffici"
        ordering = ["code"]

    def __str__(self):
        return self.name_it


class EmployeeProfile(models.Model):
    """The office an employee works for.

    Kept out of `accounts` on purpose: the user model says *what* someone is
    (their role), while the office they staff belongs to the booking slice.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        verbose_name="utente",
    )
    office = models.ForeignKey(
        Office,
        # PROTECT: an office with staff assigned must be emptied deliberately,
        # never removed as a side effect of deleting the office row.
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name="ufficio",
    )

    class Meta:
        verbose_name = "profilo dipendente"
        verbose_name_plural = "profili dipendenti"

    def __str__(self):
        return f"{self.user.email} ({self.office.code})"


class Appointment(models.Model):
    """A booked slot between a student and a specific employee.

    The employee is assigned when the booking is made, not later, so the field
    is not nullable: an appointment nobody is responsible for is not a state
    this app should be able to represent.

    Note the invariant the schema deliberately does *not* enforce: that
    ``employee.office`` equals ``office``. Expressing it in the database would
    mean duplicating the office onto every appointment row and adding a check
    constraint across a join, which Django cannot do portably. It is enforced
    at service level instead, where the employee is chosen from
    ``office.employees`` in the first place. Anything writing appointments
    outside that service — a data migration, a fixture, the admin — has to
    uphold it itself.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="studente",
    )
    office = models.ForeignKey(
        Office,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="ufficio",
    )
    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="dipendente",
    )
    slot = models.DateTimeField(verbose_name="inizio dell'appuntamento")
    status = models.CharField(
        max_length=16,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.BOOKED,
        verbose_name="stato",
    )
    question_text = models.TextField(
        verbose_name="domanda",
        help_text="La domanda scritta dallo studente, mostrata al dipendente.",
    )
    question_lang = models.CharField(
        max_length=2,
        choices=[("it", "Italiano"), ("en", "Inglese")],
        verbose_name="lingua della domanda",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="creato il")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="aggiornato il")

    class Meta:
        verbose_name = "appuntamento"
        verbose_name_plural = "appuntamenti"
        ordering = ["-slot"]
        constraints = [
            # Conditional on purpose: an employee has at most one *booked*
            # appointment per slot, so cancelling frees the slot for someone
            # else while the cancelled row stays on record.
            models.UniqueConstraint(
                fields=["employee", "slot"],
                condition=Q(status=AppointmentStatus.BOOKED),
                name="unique_booked_slot_per_employee",
            )
        ]

    def __str__(self):
        return f"{self.slot:%Y-%m-%d %H:%M} — {self.student.email} @ {self.office.code}"
