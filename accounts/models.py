from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from pronto.enums import Role


class UserManager(BaseUserManager):
    """Creates users identified by email instead of username."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        # Lowercased whole: the unique constraint is case-sensitive.
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        extra_fields["role"] = Role.ADMIN
        return self.create_user(email, password, **extra_fields)


# Stored as text to keep the leading zeros; older matricole have 6 digits.
matricola_validator = RegexValidator(
    r"^[0-9]{6,10}$", "A matricola is a number of 6 to 10 digits."
)
MATRICOLA_TAKEN = "A student with this matricola is already registered."


class User(AbstractUser):
    """University student or employee, identified by their institutional email."""

    Role = Role

    username = None  # replaced by email as the login credential
    email = models.EmailField(
        unique=True,
        verbose_name="indirizzo email",
        help_text="Indirizzo istituzionale, usato anche come credenziale di accesso.",
    )
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        verbose_name="ruolo",
        help_text="Derivato dal dominio dell'indirizzo email in fase di registrazione.",
    )
    # Required, unlike in AbstractUser.
    first_name = models.CharField(_("first name"), max_length=150)
    last_name = models.CharField(_("last name"), max_length=150)
    # Active from registration; an admin clears it to block logins.
    is_active = models.BooleanField(
        default=True,
        verbose_name="attivo",
        help_text=(
            "Toglilo per impedire all'utente di accedere, invece di eliminarne "
            "l'account."
        ),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "utente"
        verbose_name_plural = "utenti"
        constraints = [
            # The database refuses empty names too, not only full_clean().
            models.CheckConstraint(
                condition=~models.Q(first_name=""),
                name="user_first_name_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(last_name=""),
                name="user_last_name_not_empty",
            ),
        ]

    def __str__(self):
        return self.email


class StudentProfile(models.Model):
    """A student's matricola and degree programme.

    A user has one if and only if their role is STUDENT. The schema cannot
    enforce it: registration, `clean()` and the admin do.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="student_profile",
        verbose_name="utente",
    )
    matricola = models.CharField(
        max_length=10,
        unique=True,
        validators=[matricola_validator],
        error_messages={"unique": MATRICOLA_TAKEN},
        verbose_name="matricola",
        help_text="Il numero di matricola Unibo, da 6 a 10 cifre.",
    )
    degree_programme = models.CharField(
        max_length=200,
        verbose_name="corso di studi",
        help_text="Il corso di laurea a cui lo studente è iscritto.",
    )

    class Meta:
        verbose_name = "profilo studente"
        verbose_name_plural = "profili studenti"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(matricola=""),
                name="student_profile_matricola_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(degree_programme=""),
                name="student_profile_degree_programme_not_empty",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} ({self.matricola})"

    def clean(self):
        super().clean()
        # A profile being built in the admin may have no user yet.
        user = getattr(self, "user", None)
        if user is not None and user.role != Role.STUDENT:
            raise ValidationError("Only students have a student profile.")
