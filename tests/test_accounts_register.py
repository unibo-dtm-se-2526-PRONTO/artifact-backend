"""Tests for the registration endpoint."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from tests.conftest import PASSWORD

User = get_user_model()

URL = "/api/auth/register/"

# Complete, valid sign-ups; a test that needs a variation spreads one and
# overrides a key, so what it is about stands out.
STUDENT = {
    "email": "mario.rossi@studio.unibo.it",
    "password": PASSWORD,
    "first_name": "Mario",
    "last_name": "Rossi",
}
EMPLOYEE = {
    "email": "anna.bianchi@unibo.it",
    "password": PASSWORD,
    "first_name": "Anna",
    "last_name": "Bianchi",
}


@pytest.mark.django_db
def test_student_email_domain_creates_a_student(client):
    response = client.post(
        URL,
        STUDENT,
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert (
        User.objects.get(email="mario.rossi@studio.unibo.it").role == User.Role.STUDENT
    )


@pytest.mark.django_db
def test_employee_email_domain_creates_an_employee(client):
    response = client.post(
        URL,
        EMPLOYEE,
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert User.objects.get(email="anna.bianchi@unibo.it").role == User.Role.EMPLOYEE


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email",
    [
        "mario.rossi@gmail.com",
        "mario.rossi@studio.unibo.com",
        "mario.rossi@evil-unibo.it",
        "mario.rossi@sub.studio.unibo.it",
    ],
)
def test_other_email_domains_are_rejected(client, email):
    response = client.post(URL, {**STUDENT, "email": email}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not User.objects.filter(email=email).exists()


@pytest.mark.django_db
def test_role_sent_by_the_client_is_ignored(client):
    client.post(
        URL,
        {**STUDENT, "role": User.Role.EMPLOYEE},
        format="json",
    )

    assert (
        User.objects.get(email="mario.rossi@studio.unibo.it").role == User.Role.STUDENT
    )


@pytest.mark.django_db
def test_password_is_never_returned(client):
    response = client.post(
        URL,
        STUDENT,
        format="json",
    )

    assert "password" not in response.json()


@pytest.mark.django_db
def test_weak_password_is_rejected(client):
    response = client.post(URL, {**STUDENT, "password": "123"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not User.objects.exists()


@pytest.mark.django_db
def test_duplicate_email_is_rejected(client):
    client.post(URL, STUDENT, format="json")

    response = client.post(URL, STUDENT, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert User.objects.filter(email=STUDENT["email"]).count() == 1


@pytest.mark.django_db
def test_registered_user_is_inactive_until_verified(client):
    client.post(
        URL,
        STUDENT,
        format="json",
    )

    assert not User.objects.get(email="mario.rossi@studio.unibo.it").is_active


@pytest.mark.django_db
def test_registration_sends_a_verification_email(client, mailoutbox):
    client.post(
        URL,
        STUDENT,
        format="json",
    )

    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["mario.rossi@studio.unibo.it"]


@pytest.mark.django_db
def test_email_is_normalised_to_lowercase(client):
    client.post(
        URL,
        {**STUDENT, "email": "Mario.Rossi@Studio.Unibo.it"},
        format="json",
    )

    assert User.objects.get().email == "mario.rossi@studio.unibo.it"


@pytest.mark.django_db
def test_the_same_address_cannot_be_registered_twice_in_a_different_case(client):
    client.post(
        URL,
        STUDENT,
        format="json",
    )

    response = client.post(
        URL,
        {**STUDENT, "email": "Mario.Rossi@Studio.Unibo.it"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_password_too_similar_to_the_email_is_rejected(client):
    # Only caught because the password is validated against the user instance.
    response = client.post(
        URL,
        {**STUDENT, "password": "mario.rossi@studio.unibo.it"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.json()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_registration_does_not_require_authentication(client):
    response = client.post(
        URL,
        STUDENT,
        format="json",
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED


# Personal data


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [STUDENT, EMPLOYEE], ids=["student", "employee"])
def test_first_and_last_name_are_stored(client, payload):
    response = client.post(URL, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=payload["email"])
    assert (user.first_name, user.last_name) == (
        payload["first_name"],
        payload["last_name"],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [STUDENT, EMPLOYEE], ids=["student", "employee"])
@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_a_missing_name_is_rejected(client, payload, field):
    incomplete = {key: value for key, value in payload.items() if key != field}

    response = client.post(URL, incomplete, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()
    assert not User.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("blank", ["", "   "])
@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_a_blank_name_is_rejected(client, field, blank):
    response = client.post(URL, {**STUDENT, field: blank}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()


@pytest.mark.django_db
def test_names_are_trimmed(client):
    client.post(
        URL, {**STUDENT, "first_name": " Mario ", "last_name": "Rossi "}, format="json"
    )

    user = User.objects.get()
    assert (user.first_name, user.last_name) == ("Mario", "Rossi")
