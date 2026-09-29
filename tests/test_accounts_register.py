"""Tests for the registration endpoint."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import get_hasher, identify_hasher
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
    "matricola": "0001012345",
    "degree_programme": "Ingegneria e scienze informatiche",
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


# Student data


@pytest.mark.django_db
def test_a_student_is_registered_with_matricola_and_degree_programme(client):
    response = client.post(URL, STUDENT, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get()
    assert user.matricola == "0001012345"
    assert user.degree_programme == "Ingegneria e scienze informatiche"


@pytest.mark.django_db
def test_registration_returns_the_new_account_without_the_password(client):
    response = client.post(URL, STUDENT, format="json")

    assert response.json() == {
        "id": User.objects.get().id,
        "email": "mario.rossi@studio.unibo.it",
        "role": User.Role.STUDENT,
        "first_name": "Mario",
        "last_name": "Rossi",
        "matricola": "0001012345",
        "degree_programme": "Ingegneria e scienze informatiche",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["matricola", "degree_programme"])
@pytest.mark.parametrize("missing", ["absent", "", "   "])
def test_a_student_without_matricola_or_degree_programme_is_rejected(
    client, field, missing
):
    payload = {key: value for key, value in STUDENT.items() if key != field}
    if missing != "absent":
        payload[field] = missing

    response = client.post(URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()
    assert not User.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "matricola",
    ["0001012345", "0000123456", "123456", "9876543"],
    ids=["current", "current-low", "old-6-digits", "old-7-digits"],
)
def test_a_numeric_matricola_of_six_to_ten_digits_is_accepted(client, matricola):
    response = client.post(URL, {**STUDENT, "matricola": matricola}, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert User.objects.get().matricola == matricola


@pytest.mark.django_db
@pytest.mark.parametrize(
    "matricola",
    ["12345", "00010123456", "00010A2345", "0001-12345", "MRARSS00A01"],
    ids=["too-short", "too-long", "letter", "dash", "fiscal-code"],
)
def test_a_malformed_matricola_is_rejected(client, matricola):
    response = client.post(URL, {**STUDENT, "matricola": matricola}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "matricola" in response.json()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_a_matricola_already_registered_is_rejected(client):
    client.post(URL, STUDENT, format="json")

    response = client.post(
        URL, {**STUDENT, "email": "mario.rossi2@studio.unibo.it"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "matricola" in response.json()
    assert User.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field, value",
    [("matricola", "0001012345"), ("degree_programme", "Ingegneria")],
)
def test_an_employee_giving_student_data_is_rejected(client, field, value):
    # Refused rather than dropped: an employee sending a matricola has most
    # likely typed the wrong address, and silently ignoring it would hide that.
    response = client.post(URL, {**EMPLOYEE, field: value}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_an_employee_is_registered_without_student_data(client):
    response = client.post(
        URL, {**EMPLOYEE, "matricola": "", "degree_programme": ""}, format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get()
    assert (user.matricola, user.degree_programme) == ("", "")


# Passwords (NFR3)


@pytest.mark.django_db
def test_the_password_is_stored_hashed(client):
    client.post(URL, STUDENT, format="json")

    stored = User.objects.get().password
    assert PASSWORD not in stored
    # A salted hash in the format of the configured hasher, not the password
    # under another name.
    assert identify_hasher(stored).algorithm == get_hasher().algorithm
    assert User.objects.get().check_password(PASSWORD)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "password, reason",
    [
        ("Xk9#q2", "too short"),
        ("password1", "too common"),
        ("83920174650", "entirely numeric"),
        ("rossi1998", "too similar to the last name"),
    ],
    ids=["minimum-length", "common", "numeric", "similar-to-a-name"],
)
def test_every_configured_password_validator_is_enforced(client, password, reason):
    # One case per validator in AUTH_PASSWORD_VALIDATORS. The last one only
    # works because the password is checked against the whole candidate user,
    # names included.
    response = client.post(URL, {**STUDENT, "password": password}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert any(reason in message for message in response.json()["password"])
    assert not User.objects.exists()
