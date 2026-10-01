from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from pronto.enums import Role


class UserManager(BaseUserManager):
    """Creates users identified by email instead of username."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        # Lowercased whole, not just the domain: the unique constraint is
        # case-sensitive, so Mario.Rossi@ and mario.rossi@ would be two accounts.
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # Forced, not defaulted: the model starts accounts inactive, waiting for
        # the emailed verification link. A superuser has no mailbox to verify, so
        # without this override createsuperuser would produce an account that
        # cannot log in at all.
        extra_fields["is_active"] = True
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        extra_fields["role"] = Role.ADMIN
        return self.create_user(email, password, **extra_fields)


# A Unibo matricola is a number, but stored as text: the leading zeros are part
# of it. Current ones have ten digits, padded with zeros ("0001012345"); older
# ones are shorter, down to six. Nothing is padded or stripped, so a matricola
# is stored exactly as the student's university documents print it.
matricola_validator = RegexValidator(
    r"^[0-9]{6,10}$", "A matricola is a number of 6 to 10 digits."
)
# Given to the field, which the API and the admin both report.
MATRICOLA_TAKEN = "A student with this matricola is already registered."


class User(AbstractUser):
    """University student or employee, identified by their institutional email."""

    # Exposed as a nested attribute because serializers.py reads
    # ``User.Role.STUDENT`` at import time.
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
    is_active = models.BooleanField(
        default=False,
        verbose_name="attivo",
        help_text=(
            "Diventa vero quando l'utente apre il link di verifica ricevuto per email."
        ),
    )

    USERNAME_FIELD = "email"
    # Empty on purpose: createsuperuser has nothing left to ask for, since the
    # manager assigns the role itself.
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        verbose_name = "utente"
        verbose_name_plural = "utenti"

    def __str__(self):
        return self.email

    def clean(self):
        """Check the personal data a user of this role has to give.

        In ``clean()`` rather than on the fields: what is required depends on
        the role, and an admin, created from the command line, has none of it.
        The student data is not here: it lives in `StudentProfile`.
        """
        super().clean()
        errors = {}
        if self.role in (Role.STUDENT, Role.EMPLOYEE):
            for field in ("first_name", "last_name"):
                if not getattr(self, field).strip():
                    errors[field] = "This field is required."
        if errors:
            raise ValidationError(errors)


class StudentProfile(models.Model):
    """What only a student has: their matricola and degree programme.

    The counterpart of `booking.EmployeeProfile`, which holds what only an
    employee has. A table of its own rather than columns on `User`, which every
    employee and admin would leave empty. Unlike the employee's, this profile
    belongs to `accounts`: it is personal data given at registration, not
    something the booking slice assigns.

    The invariant the schema does *not* enforce: a user has a student profile
    if and only if their role is ``STUDENT``. A constraint across the two
    tables, depending on a column of the other one, is not something Django
    can express portably. Registration creates the user and the profile in one
    transaction, `clean()` refuses a profile for anyone else, and the admin
    applies both halves of the rule on the user's page. Anything writing users outside those
    paths — a data migration, a fixture, the shell — has to uphold it itself.
    """

    # The user's own key, not a column of its own: a profile is part of the
    # user, never reassigned, and there is at most one.
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
            # A required CharField still accepts "" when saved from code, since
            # only the forms check for blanks; these make the database refuse
            # it too.
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
        # getattr: a profile being built may have no user yet. The admin's
        # inline is one, and checks the role itself.
        user = getattr(self, "user", None)
        if user is not None and user.role != Role.STUDENT:
            raise ValidationError("Only students have a student profile.")
