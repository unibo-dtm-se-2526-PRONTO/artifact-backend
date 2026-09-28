"""Tests for the custom user model."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from tests.conftest import PASSWORD

User = get_user_model()


def test_user_model_is_the_configured_auth_user_model():
    assert User._meta.label == "accounts.User"


def test_email_is_the_login_credential():
    assert User.USERNAME_FIELD == "email"


def test_role_choices_are_student_and_employee():
    assert User.Role.STUDENT == "STUDENT"
    assert User.Role.EMPLOYEE == "EMPLOYEE"


@pytest.mark.django_db
def test_user_is_created_with_a_role():
    user = User.objects.create_user(
        email="mario.rossi@studio.unibo.it",
        password=PASSWORD,
        role=User.Role.STUDENT,
    )

    assert user.email == "mario.rossi@studio.unibo.it"
    assert user.role == User.Role.STUDENT


@pytest.mark.django_db
def test_password_is_hashed_and_not_stored_in_clear_text():
    user = User.objects.create_user(
        email="mario.rossi@studio.unibo.it",
        password=PASSWORD,
        role=User.Role.STUDENT,
    )

    assert user.password != PASSWORD
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_new_user_is_inactive_until_the_email_is_verified():
    user = User.objects.create_user(
        email="mario.rossi@studio.unibo.it",
        password=PASSWORD,
        role=User.Role.STUDENT,
    )

    assert not user.is_active


@pytest.mark.django_db
def test_email_is_stored_lowercase():
    user = User.objects.create_user(
        email="Mario.Rossi@Studio.Unibo.it",
        password=PASSWORD,
        role=User.Role.STUDENT,
    )

    assert user.email == "mario.rossi@studio.unibo.it"


@pytest.mark.django_db
def test_superuser_is_active_and_does_not_need_verification():
    admin = User.objects.create_superuser(email="admin@unibo.it", password=PASSWORD)

    assert admin.is_active and admin.is_staff and admin.is_superuser


@pytest.mark.django_db
def test_email_must_be_unique():
    User.objects.create_user(
        email="mario.rossi@studio.unibo.it",
        password=PASSWORD,
        role=User.Role.STUDENT,
    )

    with pytest.raises(IntegrityError):
        User.objects.create_user(
            email="mario.rossi@studio.unibo.it",
            password="another-passphrase",
            role=User.Role.STUDENT,
        )


@pytest.mark.parametrize("role", ["STUDENT", "EMPLOYEE"])
def test_students_and_employees_need_a_first_and_last_name(role):
    user = User(email="someone@unibo.it", role=role)

    with pytest.raises(ValidationError) as error:
        user.clean()

    assert {"first_name", "last_name"} <= set(error.value.message_dict)


def test_an_admin_needs_no_name():
    # createsuperuser asks for nothing but the email and the password.
    User(email="admin@unibo.it", role=User.Role.ADMIN).clean()
