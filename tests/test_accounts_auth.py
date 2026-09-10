"""Tests for the login, logout and current-user endpoints."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()

LOGIN_URL = "/api/auth/login/"
LOGOUT_URL = "/api/auth/logout/"
ME_URL = "/api/auth/me/"

PASSWORD = "s3cret-passphrase"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="mario.rossi@studio.unibo.it",
        password=PASSWORD,
        role=User.Role.STUDENT,
        is_active=True,  # already verified: these tests are about logging in
    )


@pytest.fixture
def authenticated_client(client, user):
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.mark.django_db
def test_login_with_valid_credentials_returns_a_token(client, user):
    response = client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["token"] == Token.objects.get(user=user).key


@pytest.mark.django_db
def test_login_with_wrong_password_is_rejected(client, user):
    response = client.post(
        LOGIN_URL, {"email": user.email, "password": "wrong-passphrase"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Token.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_login_with_unknown_email_is_rejected(client):
    response = client.post(
        LOGIN_URL,
        {"email": "nobody@studio.unibo.it", "password": PASSWORD},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_login_with_a_different_case_email_succeeds(client, user):
    response = client.post(
        LOGIN_URL,
        {"email": "Mario.Rossi@Studio.Unibo.it", "password": PASSWORD},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_unverified_user_cannot_log_in(client, user):
    user.is_active = False
    user.save()

    response = client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Token.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_unverified_user_gets_the_same_error_as_a_wrong_password(client, user):
    # Deliberate: a specific "not verified" message would reveal that the
    # address belongs to a registered account.
    user.is_active = False
    user.save()
    unverified = client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )

    user.is_active = True
    user.save()
    wrong_password = client.post(
        LOGIN_URL, {"email": user.email, "password": "wrong-passphrase"}, format="json"
    )

    assert unverified.json() == wrong_password.json()


@pytest.mark.django_db
def test_login_never_returns_the_password(client, user):
    response = client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )

    assert "password" not in response.json()


@pytest.mark.django_db
def test_logout_deletes_the_token(authenticated_client, user):
    response = authenticated_client.post(LOGOUT_URL)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Token.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_logout_requires_authentication(client):
    response = client.post(LOGOUT_URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_me_returns_the_authenticated_user(authenticated_client, user):
    response = authenticated_client.get(ME_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": user.id,
        "email": user.email,
        "role": User.Role.STUDENT,
    }


@pytest.mark.django_db
def test_me_requires_authentication(client):
    response = client.get(ME_URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_token_is_no_longer_accepted_after_logout(authenticated_client):
    authenticated_client.post(LOGOUT_URL)

    response = authenticated_client.get(ME_URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
