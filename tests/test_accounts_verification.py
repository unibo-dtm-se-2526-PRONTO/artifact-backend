"""Tests for the email verification link."""

from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from accounts.verification import verification_url
from tests.conftest import PASSWORD

User = get_user_model()

LOGIN_URL = "/api/auth/login/"


def verification_path(user):
    """The verification link as a path, which is what the test client wants."""
    return urlparse(verification_url(user)).path


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="mario.rossi@studio.unibo.it",
        password=PASSWORD,
        role=User.Role.STUDENT,
        first_name="Mario",
        last_name="Rossi",
        is_active=False,
    )


@pytest.mark.django_db
def test_a_valid_link_activates_the_account(client, user):
    response = client.get(verification_path(user))

    user.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert user.is_active


@pytest.mark.django_db
def test_login_succeeds_after_verification(client, user):
    client.get(verification_path(user))

    response = client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_a_tampered_token_is_rejected(client, user):
    url = verification_path(user).rstrip("/") + "x/"

    response = client.get(url)

    user.refresh_from_db()
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not user.is_active


@pytest.mark.django_db
def test_a_link_for_an_unknown_user_is_rejected(client, user):
    url = verification_path(user)
    user.delete()

    response = client.get(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
