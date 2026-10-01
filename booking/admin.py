from django.contrib import admin

from .models import Appointment, EmployeeProfile, Shift


class ShiftInline(admin.TabularInline):
    # Written straight to the table: the grid and overlap rules of
    # `declare_shift` are not applied here, so an admin has to keep to them.
    model = Shift
    extra = 0


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    inlines = [ShiftInline]
    list_display = ["user", "office"]
    list_filter = ["office"]
    search_fields = ["user__email"]
    autocomplete_fields = ["user"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["slot", "student", "office", "employee", "status"]
    list_filter = ["status", "office", "question_lang"]
    search_fields = ["student__email", "question_text"]
    date_hierarchy = "slot"
    autocomplete_fields = ["student"]
    readonly_fields = ["created_at", "updated_at"]
