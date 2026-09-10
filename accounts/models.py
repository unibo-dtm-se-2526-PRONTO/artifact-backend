from django.contrib.auth.models import AbstractUser, BaseUserManager
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
