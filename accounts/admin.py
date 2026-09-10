from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm

from .models import User


class UserCreationFormWithoutUsername(UserCreationForm):
    """Django's own creation form, retargeted at email as the credential."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "role")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Subclassed rather than reused as is: every fieldset and every list in
    Django's UserAdmin names ``username``, a field this model does not have.
    """

    add_form = UserCreationFormWithoutUsername

    list_display = ["email", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email"]
    ordering = ["email"]

    fieldsets = [
        (None, {"fields": ("email", "password")}),
        ("Anagrafica", {"fields": ("first_name", "last_name")}),
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
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    ]
