"""Enumerations shared across the project's apps."""

from django.db import models


class Role(models.TextChoices):
    """What a user is allowed to do, derived from their institutional email."""

    STUDENT = "STUDENT", "Student"
    EMPLOYEE = "EMPLOYEE", "Employee"
