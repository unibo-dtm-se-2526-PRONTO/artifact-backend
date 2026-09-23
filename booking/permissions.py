from rest_framework.permissions import BasePermission

from pronto.enums import Role


class IsStudent(BasePermission):
    """Only students book appointments; employees are the ones who answer them.

    Read through ``getattr`` rather than ``request.user.role``: an anonymous
    user has no role, and this has to deny rather than raise if it is ever used
    without ``IsAuthenticated`` in front of it.
    """

    message = "Only students can book an appointment."

    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == Role.STUDENT


class IsEmployee(BasePermission):
    """Only the staff close an appointment: they are the ones who were there.

    Load-bearing rather than decorative. `AppointmentQuerysetMixin` scopes an
    appointment to the caller, so a student reaches their own appointment
    perfectly well; without this check they could declare their own question
    answered. Read through ``getattr`` for the same reason as `IsStudent`.
    """

    message = "Only the employee handling an appointment can complete it."

    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == Role.EMPLOYEE
