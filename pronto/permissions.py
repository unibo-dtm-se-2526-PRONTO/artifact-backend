"""Who may call what, by role.

Here rather than in an app, like `pronto.enums`: `booking` and `faq` both
restrict endpoints to students, and `booking` already depends on `faq`, so
`faq` importing from `booking` would close a cycle.
"""

from rest_framework.permissions import BasePermission

from pronto.enums import Role


class IsStudent(BasePermission):
    """Only students ask questions and book appointments; employees answer them.

    Read through ``getattr`` rather than ``request.user.role``: an anonymous
    user has no role, and this has to deny rather than raise if it is ever used
    without ``IsAuthenticated`` in front of it.
    """

    message = "Only students can do this."

    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == Role.STUDENT


class IsEmployee(BasePermission):
    """Only the staff close appointments and set up their own availability.

    Load-bearing rather than decorative on completion. `AppointmentQuerysetMixin`
    scopes an appointment to the caller, so a student reaches their own
    appointment perfectly well; without this check they could declare their own
    question answered. Read through ``getattr`` for the same reason as
    `IsStudent`.
    """

    message = "Only employees can do this."

    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == Role.EMPLOYEE
