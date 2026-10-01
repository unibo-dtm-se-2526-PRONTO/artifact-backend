"""Tests for the login, logout and current-user endpoints."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token

from tests.conftest import PASSWORD, authenticate, make_user

User = get_user_model()

LOGIN_URL = "/api/auth/login/"
LOGOUT_URL = "/api/auth/logout/"
ME_URL = "/api/auth/me/"


@pytest.fixture
def user(db):
    # Already verified, as make_user makes them: these tests are about logging in.
    return make_user(
        "mario.rossi@studio.unibo.it",
        User.Role.STUDENT,
        first_name="Mario",
        last_name="Rossi",
        matricola="0001012345",
        degree_programme="Ingegneria e scienze informatiche",
    )


@pytest.fixture
def authenticated_client(user):
    return authenticate(user)


@pytest.mark.django_db
def test_login_with_valid_credentials_returns_a_token(client, user):
    response = client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["token"] == Token.objects.get(user=user).key


@pytest.mark.django_db
def test_login_records_the_time_of_the_login(client, user):
    assert user.last_login is None
    before = timezone.now()

    client.post(LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json")

    user.refresh_from_db()
    assert before <= user.last_login <= timezone.now()


@pytest.mark.django_db
def test_every_login_updates_the_last_login(client, user):
    credentials = {"email": user.email, "password": PASSWORD}
    client.post(LOGIN_URL, credentials, format="json")
    user.refresh_from_db()
    first = user.last_login

    client.post(LOGIN_URL, credentials, format="json")

    user.refresh_from_db()
    assert user.last_login > first


@pytest.mark.django_db
def test_a_failed_login_records_nothing(client, user):
    client.post(
        LOGIN_URL, {"email": user.email, "password": "wrong-passphrase"}, format="json"
    )

    user.refresh_from_db()
    assert user.last_login is None


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
        "first_name": "Mario",
        "last_name": "Rossi",
        "matricola": "0001012345",
        "degree_programme": "Ingegneria e scienze informatiche",
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


@pytest.mark.django_db
def test_me_gives_an_employee_no_student_data(db):
    employee = make_user(
        "anna.bianchi@unibo.it",
        User.Role.EMPLOYEE,
        first_name="Anna",
        last_name="Bianchi",
    )

    response = authenticate(employee).get(ME_URL)

    assert response.json() == {
        "id": employee.id,
        "email": "anna.bianchi@unibo.it",
        "role": User.Role.EMPLOYEE,
        "first_name": "Anna",
        "last_name": "Bianchi",
        "matricola": "",
        "degree_programme": "",
    }


@pytest.mark.django_db
def test_no_endpoint_ever_returns_the_password_or_its_hash(client):
    # NFR3, across the whole sign-up flow: neither the password the user typed
    # nor the hash stored in its place appears in any response body.
    register = client.post(
        "/api/auth/register/",
        {
            "email": "anna.bianchi@unibo.it",
            "password": PASSWORD,
            "first_name": "Anna",
            "last_name": "Bianchi",
        },
        format="json",
    )
    user = User.objects.get()
    user.is_active = True
    user.save()
    login = client.post(
        LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Token {login.json()['token']}")
    me = client.get(ME_URL)

    for response in (register, login, me):
        assert response.status_code < 300
        body = response.content.decode()
        assert PASSWORD not in body
        assert user.password not in body
        assert "password" not in response.json()
