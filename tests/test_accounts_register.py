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
def test_registration_does_not_require_authentication(client):
    response = client.post(
        URL,
        {"email": "mario.rossi@studio.unibo.it", "password": "s3cret-passphrase"},
        format="json",
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED
