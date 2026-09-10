"""Tests for the registration endpoint."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

URL = "/api/auth/register/"


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_student_email_domain_creates_a_student(client):
    response = client.post(
        URL,
        {"email": "mario.rossi@studio.unibo.it", "password": "s3cret-passphrase"},
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
        {"email": "anna.bianchi@unibo.it", "password": "s3cret-passphrase"},
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
    response = client.post(
        URL, {"email": email, "password": "s3cret-passphrase"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not User.objects.filter(email=email).exists()


@pytest.mark.django_db
def test_role_sent_by_the_client_is_ignored(client):
    client.post(
        URL,
        {
            "email": "mario.rossi@studio.unibo.it",
            "password": "s3cret-passphrase",
            "role": User.Role.EMPLOYEE,
        },
        format="json",
    )

    assert (
        User.objects.get(email="mario.rossi@studio.unibo.it").role == User.Role.STUDENT
    )


@pytest.mark.django_db
def test_password_is_never_returned(client):
    response = client.post(
        URL,
        {"email": "mario.rossi@studio.unibo.it", "password": "s3cret-passphrase"},
        format="json",
    )

    assert "password" not in response.json()


@pytest.mark.django_db
def test_weak_password_is_rejected(client):
    response = client.post(
        URL, {"email": "mario.rossi@studio.unibo.it", "password": "123"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not User.objects.exists()


@pytest.mark.django_db
def test_duplicate_email_is_rejected(client):
    payload = {"email": "mario.rossi@studio.unibo.it", "password": "s3cret-passphrase"}
    client.post(URL, payload, format="json")

    response = client.post(URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert User.objects.filter(email=payload["email"]).count() == 1


@pytest.mark.django_db
def test_registered_user_is_inactive_until_verified(client):
    client.post(
        URL,
        {"email": "mario.rossi@studio.unibo.it", "password": "s3cret-passphrase"},
        format="json",
    )

    assert not User.objects.get(email="mario.rossi@studio.unibo.it").is_active


@pytest.mark.django_db
def test_registration_sends_a_verification_email(client, mailoutbox):
    client.post(
        URL,
        {"email": "mario.rossi@studio.unibo.it", "password": "s3cret-passphrase"},
        format="json",
    )

    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["mario.rossi@studio.unibo.it"]


@pytest.mark.django_db
def test_email_is_normalised_to_lowercase(client):
    client.post(
        URL,
        {"email": "Mario.Rossi@Studio.Unibo.it", "password": "s3cret-passphrase"},
        format="json",
    )

    assert User.objects.get().email == "mario.rossi@studio.unibo.it"


@pytest.mark.django_db
def test_the_same_address_cannot_be_registered_twice_in_a_different_case(client):
    client.post(
        URL,
        {"email": "mario.rossi@studio.unibo.it", "password": "s3cret-passphrase"},
        format="json",
    )

    response = client.post(
        URL,
        {"email": "Mario.Rossi@Studio.Unibo.it", "password": "s3cret-passphrase"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_password_too_similar_to_the_email_is_rejected(client):
    # Only caught because the password is validated against the user instance.
    response = client.post(
        URL,
        {
            "email": "mario.rossi@studio.unibo.it",
            "password": "mario.rossi@studio.unibo.it",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.json()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_registration_does_not_require_authentication(client):
    response = client.post(
        URL,
        {"email": "mario.rossi@studio.unibo.it", "password": "s3cret-passphrase"},
        format="json",
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED
