from django.contrib import admin

from .models import Faq, Inquiry


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ["office_code", "question_it", "is_active", "updated_at"]
    list_filter = ["office_code", "is_active"]
    search_fields = ["question_it", "question_en", "answer_it", "answer_en"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    """What students asked, to see where the knowledge base falls short.

    Read-only: an inquiry is a record of what happened, written by the API.
    Deleting stays possible, to drop a question that should not have been
    stored (a student writing their own personal data into it, say).
    """

    list_display = [
        "created_at",
        "office_code",
        "text",
        "matched_faq",
        "score",
        "matched_by",
        "resolved",
    ]
    list_filter = ["office_code", "language", "matched_by", "resolved"]
    search_fields = ["text"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "id",
        "office_code",
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
