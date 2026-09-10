from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "role", "is_staff"]
    list_filter = ["role", "is_staff"]
    search_fields = ["email"]
