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
        extra_fields.setdefault("is_active", False)  # until the email is verified
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.EMPLOYEE)
        extra_fields["is_active"] = True  # no mailbox to verify
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """University student or employee, identified by their institutional email."""

    Role = Role

    username = None  # replaced by email as the login credential
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=8, choices=Role.choices)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["role"]

    objects = UserManager()

    def __str__(self):
        return self.email
