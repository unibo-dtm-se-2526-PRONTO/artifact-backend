from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from pronto.enums import Role

from .models import StudentProfile, User


class UserCreationFormWithoutUsername(AdminUserCreationForm):
    """Django's admin creation form, with email as the credential."""

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = (
            "email",
            "role",
            "first_name",
            "last_name",
        )


class StudentProfileFormSet(BaseInlineFormSet):
    """Requires a profile for a student and refuses one to anybody else."""

    def clean(self):
        super().clean()
        kept = [
            form
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        if self.instance.role == Role.STUDENT and not kept:
            raise ValidationError("A student needs a matricola and a degree programme.")
        if self.instance.role != Role.STUDENT and kept:
            raise ValidationError("Only students have a student profile.")


class StudentProfileInline(admin.StackedInline):
    """The student data, edited on the user's page."""

    model = StudentProfile
    formset = StudentProfileFormSet

    def get_extra(self, request, obj=None, **kwargs):
        if obj is not None and obj.role != Role.STUDENT:
            return 0
        return 1


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Django's UserAdmin without ``username``."""

    add_form = UserCreationFormWithoutUsername
    inlines = [StudentProfileInline]

    list_display = ["email", "last_name", "first_name", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = [
        "email",
        "last_name",
        "first_name",
        "student_profile__matricola",
    ]
    ordering = ["email"]

    fieldsets = [
        (None, {"fields": ("email", "password")}),
        (
            "Anagrafica",
            {"fields": ("first_name", "last_name")},
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
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    ]
