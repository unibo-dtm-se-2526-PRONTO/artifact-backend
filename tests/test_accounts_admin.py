"""Tests for the user pages of the admin, student profile included."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from accounts.models import StudentProfile
from tests.conftest import PASSWORD, make_user

User = get_user_model()

ADD_URL = "/admin/accounts/user/add/"
LIST_URL = "/admin/accounts/user/"


@pytest.fixture
def admin(db):
    client = Client()
    client.force_login(
        User.objects.create_superuser(
            email="admin@unibo.it",
            password=PASSWORD,
            first_name="Ada",
            last_name="Admin",
        )
    )
    return client


def add_form(email, role, profile=None):
    """What the add page posts: the user, and the student profile inline."""
    data = {
        "email": email,
        "role": role,
        "first_name": "Mario",
        "last_name": "Rossi",
        "usable_password": "true",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "student_profile-TOTAL_FORMS": "1",
        "student_profile-INITIAL_FORMS": "0",
        "student_profile-MIN_NUM_FORMS": "0",
        "student_profile-MAX_NUM_FORMS": "1",
    }
    for field, value in (profile or {}).items():
        data[f"student_profile-0-{field}"] = value
    return data


PROFILE = {"matricola": "0001012345", "degree_programme": "Ingegneria"}


def test_a_student_is_added_with_their_profile(admin):
    response = admin.post(
        ADD_URL, add_form("mario.rossi@studio.unibo.it", "STUDENT", PROFILE)
    )

    assert response.status_code == 302
    profile = User.objects.get(email="mario.rossi@studio.unibo.it").student_profile
    assert (profile.matricola, profile.degree_programme) == (
        "0001012345",
        "Ingegneria",
    )


def test_a_student_cannot_be_added_without_a_profile(admin):
    response = admin.post(ADD_URL, add_form("mario.rossi@studio.unibo.it", "STUDENT"))

    assert response.status_code == 200
    assert "A student needs a matricola and a degree programme." in (
        response.content.decode()
    )
    assert not User.objects.filter(email="mario.rossi@studio.unibo.it").exists()


def test_an_employee_cannot_be_given_a_student_profile(admin):
    response = admin.post(
        ADD_URL, add_form("anna.bianchi@unibo.it", "EMPLOYEE", PROFILE)
    )

    assert response.status_code == 200
    assert "Only students have a student profile." in response.content.decode()
    assert not StudentProfile.objects.exists()


def test_an_employee_is_added_without_a_profile(admin):
    response = admin.post(ADD_URL, add_form("anna.bianchi@unibo.it", "EMPLOYEE"))

    assert response.status_code == 302
    assert User.objects.filter(email="anna.bianchi@unibo.it").exists()
    assert not StudentProfile.objects.exists()


def test_the_student_profile_is_shown_on_the_user_page(admin):
    student = make_user(
        "mario.rossi@studio.unibo.it",
        User.Role.STUDENT,
        first_name="Mario",
        last_name="Rossi",
        matricola="0001012345",
    )

    response = admin.get(f"{LIST_URL}{student.pk}/change/")

    assert response.status_code == 200
    assert 'value="0001012345"' in response.content.decode()


def test_users_can_be_searched_by_matricola(admin):
    make_user(
        "mario.rossi@studio.unibo.it",
        User.Role.STUDENT,
        first_name="Mario",
        last_name="Rossi",
        matricola="0001012345",
    )
    make_user(
        "lucia.neri@studio.unibo.it",
        User.Role.STUDENT,
        first_name="Lucia",
        last_name="Neri",
        matricola="0001099999",
    )

    response = admin.get(LIST_URL, {"q": "0001012345"})

    body = response.content.decode()
    assert "mario.rossi@studio.unibo.it" in body
    assert "lucia.neri@studio.unibo.it" not in body
