from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from pronto.enums import Role

from .models import StudentProfile, User


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
        )


class StudentProfileFormSet(BaseInlineFormSet):
    """Asks a student for their profile, and refuses one to anybody else.

    Checked here rather than left to `StudentProfile.clean()`: the inline's
    profile only gets its user when saved, so its own check cannot see the
    role. This one reads it from the user as edited on the same page.
    """

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
    """The student data, edited on the user's own page.

    One at most: Django caps the inline at one form, the relation being
    one-to-one.
    """

    model = StudentProfile
    formset = StudentProfileFormSet

    def get_extra(self, request, obj=None, **kwargs):
        # No empty profile form on the page of an employee or an admin; one
        # can still be added, and is then refused unless the role changes too.
        if obj is not None and obj.role != Role.STUDENT:
            return 0
        return 1


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Subclassed rather than reused as is: every fieldset and every list in
    Django's UserAdmin names ``username``, a field this model does not have.
    """

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
