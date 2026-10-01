from django.conf import settings
from django.db import models
from django.db.models import F, Q

from offices.models import Office
from pronto.enums import AppointmentStatus


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
    """A stretch of a weekday an employee is on duty, every week.

    Shifts are what an office's availability is computed from (FR4): the slots
    are never stored. The times are the helpdesk's local ones (``TIME_ZONE``).

    Two rules live in the service rather than here, because they depend on
    other rows: a shift sits on its office's slot grid, and it overlaps no
    other shift of the same employee (see `booking.services.declare_shift`).
    As with `Appointment`, anything writing shifts outside that service has to
    uphold them itself.
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
    # The FAQ the student was shown and did not find helpful, so the employee
    # starts from what the student already knows. Optional: there may have been
    # no match at all. The dependency runs one way only — `faq` knows nothing
    # of appointments, hence no reverse accessor.
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
