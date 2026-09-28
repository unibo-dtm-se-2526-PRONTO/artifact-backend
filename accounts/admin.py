from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm

from .models import User


class UserCreationFormWithoutUsername(AdminUserCreationForm):
    """Django's own admin creation form, retargeted at email as the credential.

    The admin one, not ``UserCreationForm``: only it declares the
    ``usable_password`` field that ``add_fieldsets`` lists, and with the plain
    form the add page fails with a ``FieldError`` before it renders.
    """

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = (
            "email",
            "role",
            "first_name",
            "last_name",
            "matricola",
            "degree_programme",
        )


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Subclassed rather than reused as is: every fieldset and every list in
    Django's UserAdmin names ``username``, a field this model does not have.
    """

    add_form = UserCreationFormWithoutUsername

    list_display = ["email", "last_name", "first_name", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "last_name", "first_name", "matricola"]
    ordering = ["email"]

    fieldsets = [
        (None, {"fields": ("email", "password")}),
        (
            "Anagrafica",
            {"fields": ("first_name", "last_name", "matricola", "degree_programme")},
        ),
        (
            "Ruolo e permessi",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Date", {"fields": ("last_login", "date_joined")}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "role",
                    "first_name",
                    "last_name",
                    "matricola",
                    "degree_programme",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    ]
