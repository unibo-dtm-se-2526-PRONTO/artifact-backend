from django.contrib import admin

from .models import Faq


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ["office_code", "question_it", "is_active", "updated_at"]
    list_filter = ["office_code", "is_active"]
    search_fields = ["question_it", "question_en", "answer_it", "answer_en"]
    readonly_fields = ["created_at", "updated_at"]
