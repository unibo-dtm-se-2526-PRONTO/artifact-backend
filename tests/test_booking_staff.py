"""Tests for the endpoints employees use to set up their availability.

The rules behind them live in `test_booking_shifts.py`; what is checked here is
the HTTP contract — who may call what, what comes back, and which refusals
reach the client and how.
"""

from datetime import time

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from booking.models import EmployeeProfile, Shift
from booking.services import book_appointment
from pronto.enums import OfficeCode, Role
from tests.conftest import authenticate, make_employee, make_user, slot_at

PROFILE_URL = "/api/employee-profile/"
SHIFTS_URL = "/api/shifts/"

MONDAY = 0


def shift_url(shift_id):
    return f"{SHIFTS_URL}{shift_id}/"


@pytest.fixture
def newcomer(db):
    """An employee who has just registered: an account, no office yet."""
    return make_user("nuovo.arrivato@unibo.it", Role.EMPLOYEE)


@pytest.fixture
def newcomer_client(newcomer):
    return authenticate(newcomer)


# --- /api/employee-profile/ --------------------------------------------------


@pytest.mark.django_db
def test_profile_requires_a_token(office):
    response = APIClient().post(PROFILE_URL, {"office": office.code})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_a_student_has_no_employee_profile(student_client, office):
    response = student_client.post(PROFILE_URL, {"office": office.code})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not EmployeeProfile.objects.exists()


@pytest.mark.django_db
def test_an_employee_chooses_their_office(newcomer_client, newcomer, office):
    response = newcomer_client.post(PROFILE_URL, {"office": office.code})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {"office": OfficeCode.GUIDANCE}
    assert EmployeeProfile.objects.get(user=newcomer).office == office


@pytest.mark.django_db
def test_the_office_is_chosen_only_once(
    newcomer_client, newcomer, office, other_office
):
    """Changing office would strand the appointments already booked with the
    old one, so after the first choice only an admin can move someone."""
    newcomer_client.post(PROFILE_URL, {"office": office.code})

    response = newcomer_client.post(PROFILE_URL, {"office": other_office.code})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "detail" in response.json()
    assert EmployeeProfile.objects.get(user=newcomer).office == office


@pytest.mark.django_db
def test_an_unknown_office_is_a_field_error(newcomer_client):
    response = newcomer_client.post(PROFILE_URL, {"office": "NOWHERE"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "office" in response.json()


@pytest.mark.django_db
def test_an_inactive_office_cannot_be_chosen(newcomer_client, office):
    office.is_active = False
    office.save()

    response = newcomer_client.post(PROFILE_URL, {"office": office.code})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "office" in response.json()


@pytest.mark.django_db
def test_an_employee_reads_back_their_office(employee_client):
    response = employee_client.get(PROFILE_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"office": OfficeCode.GUIDANCE}


@pytest.mark.django_db
def test_reading_a_profile_not_yet_chosen_is_a_404(newcomer_client):
    response = newcomer_client.get(PROFILE_URL)

    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- /api/shifts/ ------------------------------------------------------------


@pytest.mark.django_db
def test_shifts_require_a_token():
    response = APIClient().get(SHIFTS_URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_a_student_has_no_shifts(student_client):
    response = student_client.get(SHIFTS_URL)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_an_employee_lists_their_own_shifts(employee_client, employee, office):
    make_employee(office, "luca.verdi@unibo.it")

    response = employee_client.get(SHIFTS_URL)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [shift["weekday"] for shift in body] == [0, 1, 2, 3, 4]
    assert body[0] == {
        "id": employee.shifts.get(weekday=MONDAY).pk,
        "weekday": MONDAY,
        "start_time": "09:00:00",
        "end_time": "17:00:00",
    }


@pytest.mark.django_db
def test_an_employee_without_an_office_has_no_shifts_yet(newcomer_client):
    response = newcomer_client.get(SHIFTS_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


@pytest.mark.django_db
def test_an_employee_declares_a_shift(office):
    employee = make_employee(office, shifts=[])
    client = authenticate(employee.user)

    response = client.post(
        SHIFTS_URL, {"weekday": MONDAY, "start_time": "09:00", "end_time": "12:00"}
    )

    assert response.status_code == status.HTTP_201_CREATED
    shift = Shift.objects.get(employee=employee)
    assert response.json() == {
        "id": shift.pk,
        "weekday": MONDAY,
        "start_time": "09:00:00",
        "end_time": "12:00:00",
    }


@pytest.mark.django_db
def test_declaring_a_shift_needs_an_office_first(newcomer_client):
    response = newcomer_client.post(
        SHIFTS_URL, {"weekday": MONDAY, "start_time": "09:00", "end_time": "12:00"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "detail" in response.json()


@pytest.mark.django_db
def test_a_shift_the_rules_refuse_is_a_400(employee_client, employee):
    """Monday 9-17 is already declared by the fixture: this one overlaps."""
    response = employee_client.post(
        SHIFTS_URL, {"weekday": MONDAY, "start_time": "10:00", "end_time": "11:00"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "detail" in response.json()
    assert employee.shifts.count() == 5


@pytest.mark.django_db
def test_an_invalid_weekday_is_a_field_error(employee_client):
    response = employee_client.post(
        SHIFTS_URL, {"weekday": 7, "start_time": "09:00", "end_time": "12:00"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "weekday" in response.json()


@pytest.mark.django_db
def test_an_employee_withdraws_a_shift(employee_client, employee):
    monday = employee.shifts.get(weekday=MONDAY)

    response = employee_client.delete(shift_url(monday.pk))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Shift.objects.filter(pk=monday.pk).exists()


@pytest.mark.django_db
def test_someone_elses_shift_is_a_404(employee_client, office):
    colleague = make_employee(office, "luca.verdi@unibo.it")
    theirs = colleague.shifts.get(weekday=MONDAY)

    response = employee_client.delete(shift_url(theirs.pk))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Shift.objects.filter(pk=theirs.pk).exists()


@pytest.mark.django_db
def test_a_shift_holding_appointments_is_kept_and_they_are_listed(
    employee_client, employee, office, student, day
):
    appointment = book_appointment(
        student=student,
        office=office,
        slot=slot_at(day, 10),
        question_text="Vorrei informazioni sul piano di studi.",
        question_lang="it",
    )
    monday = employee.shifts.get(weekday=MONDAY)

    response = employee_client.delete(shift_url(monday.pk))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["appointments"] == [appointment.pk]
    assert Shift.objects.filter(pk=monday.pk).exists()


@pytest.mark.django_db
def test_shifts_cannot_be_edited_in_place(employee_client, employee):
    """Replacing a shift is a withdrawal and a new declaration, so both
    rules — the grid and the booked appointments — apply to every change."""
    monday = employee.shifts.get(weekday=MONDAY)

    response = employee_client.patch(shift_url(monday.pk), {"end_time": "12:00"})

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    monday.refresh_from_db()
    assert monday.end_time == time(17)
