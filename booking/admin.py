from django.contrib import admin

from .models import Appointment, EmployeeProfile, Office


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name_it",
        "contact_email",
        "slot_duration_minutes",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["code", "name_it", "name_en"]


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
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
