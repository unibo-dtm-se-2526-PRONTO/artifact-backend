from django.conf import settings
from django.db import models
from django.db.models import F, Q

from offices.models import Office
from pronto.enums import AppointmentStatus, Language


class EmployeeProfile(models.Model):
    """The office an employee works for."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        verbose_name="utente",
    )
    office = models.ForeignKey(
        Office,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name="ufficio",
    )

    class Meta:
        verbose_name = "profilo dipendente"
        verbose_name_plural = "profili dipendenti"

    def __str__(self):
        return f"{self.user.email} ({self.office.code})"


class Weekday(models.IntegerChoices):
    """Days of the week, numbered as ``date.weekday()`` numbers them."""

    MONDAY = 0, "lunedì"
    TUESDAY = 1, "martedì"
    WEDNESDAY = 2, "mercoledì"
    THURSDAY = 3, "giovedì"
    FRIDAY = 4, "venerdì"
    SATURDAY = 5, "sabato"
    SUNDAY = 6, "domenica"


class Shift(models.Model):
    """A weekly stretch of a weekday an employee is on duty, in local time.

    Grid and overlap rules are checked by `booking.services.declare_shift`.
    """

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name="shifts",
        verbose_name="dipendente",
    )
    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices, verbose_name="giorno della settimana"
    )
    start_time = models.TimeField(verbose_name="inizio")
    end_time = models.TimeField(verbose_name="fine")

    class Meta:
        verbose_name = "turno"
        verbose_name_plural = "turni"
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")),
                name="shift_ends_after_it_starts",
            )
        ]

    def __str__(self):
        return (
            f"{self.employee.user.email}: {self.get_weekday_display()} "
            f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        )


class Appointment(models.Model):
    """A booked slot between a student and a specific employee.

    That ``employee.office`` equals ``office`` is enforced by `booking.services`,
    not by the schema.
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
        choices=Language.choices,
        verbose_name="lingua della domanda",
    )
    # The FAQ the student did not find helpful, if any.
    suggested_faq = models.ForeignKey(
        "faq.Faq",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="FAQ proposta",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="creato il")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="aggiornato il")

    class Meta:
        verbose_name = "appuntamento"
        verbose_name_plural = "appuntamenti"
        ordering = ["-slot"]
        constraints = [
            # Only BOOKED rows count, so cancelling frees the slot.
            models.UniqueConstraint(
                fields=["employee", "slot"],
                condition=Q(status=AppointmentStatus.BOOKED),
                name="unique_booked_slot_per_employee",
            )
        ]

    def __str__(self):
        return f"{self.slot:%Y-%m-%d %H:%M} — {self.student.email} @ {self.office.code}"
