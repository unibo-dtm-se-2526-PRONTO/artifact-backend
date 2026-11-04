"""Permissions by role, shared by `booking` and `faq`."""

from rest_framework.permissions import BasePermission

from pronto.enums import Role


class IsStudent(BasePermission):
    """Students only. ``getattr`` so an anonymous user is denied, not an error."""

    message = "Only students can do this."

    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == Role.STUDENT


class IsEmployee(BasePermission):
    """Employees only, e.g. to complete an appointment or declare shifts."""

    message = "Only employees can do this."

    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == Role.EMPLOYEE
