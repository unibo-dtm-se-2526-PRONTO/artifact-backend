from django.contrib import admin

from .models import Office


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
