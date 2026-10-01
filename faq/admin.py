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
    """What students asked, to see where the knowledge base falls short.

    Read-only: an inquiry is a record of what happened, written by the API.
    Deleting stays possible, to drop a question that should not have been
    stored (a student writing their own personal data into it, say).
    """

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
    # The office and the FAQ are both shown, and a FAQ is shown with its own
    # office's code: one join for all of them instead of a query per row.
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
