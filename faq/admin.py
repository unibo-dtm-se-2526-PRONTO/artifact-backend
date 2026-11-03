from django.contrib import admin

from .models import Faq, Inquiry


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ["office", "question_it", "is_active", "updated_at"]
    list_filter = ["office", "is_active"]
    list_select_related = ["office"]
    search_fields = [
        "question_it",
        "question_en",
        "answer_it",
        "answer_en",
        "office__code",
        "office__name_it",
    ]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    """Students' questions, read-only; deleting is allowed."""

    list_display = [
        "created_at",
        "office",
        "text",
        "matched_faq",
        "score",
        "matched_by",
        "resolved",
    ]
    list_filter = ["office", "language", "matched_by", "resolved"]
    list_select_related = ["office", "matched_faq__office"]
    search_fields = ["text", "office__code", "office__name_it"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "id",
        "office",
        "text",
        "language",
        "matched_faq",
        "score",
        "matched_by",
        "resolved",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False
