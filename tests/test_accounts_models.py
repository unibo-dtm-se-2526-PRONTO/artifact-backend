"""Tests for the custom user model."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from accounts.models import StudentProfile
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


# Student profile


def student_profile(**fields):
    """A complete, valid profile of a student not yet saved; `fields` overrides."""
    user = User(
        email="mario.rossi@studio.unibo.it",
        role=User.Role.STUDENT,
        first_name="Mario",
        last_name="Rossi",
    )
    return StudentProfile(
        **{
            "user": user,
            "matricola": "0001012345",
            "degree_programme": "Ingegneria e scienze informatiche",
            **fields,
        }
    )


@pytest.mark.django_db
def test_a_complete_student_profile_is_valid():
    student_profile().full_clean(exclude=["user"])


@pytest.mark.django_db
def test_a_student_profile_needs_a_matricola_and_a_degree_programme():
    with pytest.raises(ValidationError) as error:
        student_profile(matricola="", degree_programme="").full_clean(exclude=["user"])

    assert set(error.value.message_dict) == {"matricola", "degree_programme"}


@pytest.mark.parametrize("role", ["EMPLOYEE", "ADMIN"])
def test_only_students_have_a_student_profile(role):
    profile = student_profile()
    profile.user.role = role

    with pytest.raises(ValidationError) as error:
        profile.clean()

    assert error.value.messages == ["Only students have a student profile."]


@pytest.mark.django_db
@pytest.mark.parametrize("matricola", ["12345", "00010123456", "00010A2345"])
def test_a_malformed_matricola_fails_validation(matricola):
    with pytest.raises(ValidationError) as error:
        student_profile(matricola=matricola).full_clean(exclude=["user"])

    assert "matricola" in error.value.message_dict


def make_student(email, matricola="0001012345"):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=User.Role.STUDENT,
        first_name="Mario",
        last_name="Rossi",
    )
    return StudentProfile.objects.create(
        user=user, matricola=matricola, degree_programme="Ingegneria"
    )


@pytest.mark.django_db
def test_the_profile_shares_the_key_of_its_user():
    profile = make_student("mario.rossi@studio.unibo.it")

    assert profile.pk == profile.user.pk
    assert profile.user.student_profile == profile


@pytest.mark.django_db
def test_two_students_cannot_share_a_matricola():
    make_student("mario.rossi@studio.unibo.it")

    with pytest.raises(IntegrityError):
        make_student("lucia.neri@studio.unibo.it")


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["matricola", "degree_programme"])
def test_the_database_refuses_an_empty_student_field(field):
    # Saved from code, nothing but the database stops it: only full_clean()
    # knows the fields are required.
    profile = make_student("mario.rossi@studio.unibo.it")
    setattr(profile, field, "")

    with pytest.raises(IntegrityError):
        profile.save()


@pytest.mark.django_db
def test_deleting_a_user_deletes_their_student_profile():
    make_student("mario.rossi@studio.unibo.it").user.delete()

    assert not StudentProfile.objects.exists()


def test_the_student_data_is_not_on_the_user_table():
    # Nobody but a student has any, so the user row has no column for it.
    columns = {field.name for field in User._meta.get_fields()}

    assert not {"matricola", "degree_programme"} & columns
