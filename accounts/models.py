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
# Given both to the field, which is what the API reports, and to the
# constraint, which is what the admin reports.
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
    # Students only, and required of them. Blank by default, and not NULL, so
    # the accounts that predate these columns, employees and admins included,
    # stay valid rows; clean() enforces them by role.
    matricola = models.CharField(
        max_length=10,
        blank=True,
        default="",
        validators=[matricola_validator],
        error_messages={"unique": MATRICOLA_TAKEN},
        verbose_name="matricola",
        help_text="Solo per gli studenti: il numero di matricola Unibo, da 6 a 10 cifre.",
    )
    degree_programme = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="corso di studi",
        help_text="Solo per gli studenti: il corso di laurea a cui sono iscritti.",
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
        constraints = [
            # Unique among the matricole actually given: everybody who is not a
            # student has an empty one.
            models.UniqueConstraint(
                fields=["matricola"],
                condition=~models.Q(matricola=""),
                name="unique_matricola",
                violation_error_message=MATRICOLA_TAKEN,
            ),
        ]

    def __str__(self):
        return self.email

    def clean(self):
        """Check the personal data a user of this role has to give.

        In ``clean()`` rather than on the fields: what is required depends on
        the role, and an admin, created from the command line, has none of it.
        The columns stay blank-able so the accounts that predate them are still
        valid rows; this is what registration and the admin forms enforce.
        """
        super().clean()
        errors = {}
        if self.role in (Role.STUDENT, Role.EMPLOYEE):
            for field in ("first_name", "last_name"):
                if not getattr(self, field).strip():
                    errors[field] = "This field is required."
        for field in ("matricola", "degree_programme"):
            given = bool(getattr(self, field).strip())
            if self.role == Role.STUDENT and not given:
                errors[field] = "This field is required."
            elif self.role != Role.STUDENT and given:
                errors[field] = "Only students have this field."
        if errors:
            raise ValidationError(errors)
