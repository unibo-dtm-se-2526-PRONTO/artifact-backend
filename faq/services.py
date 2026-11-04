"""Asking a question and closing it (US2a-US2c)."""

from .matching import find_best_match
from .models import Inquiry


class InquiryError(Exception):
    """A request about an inquiry that cannot be honoured."""


def ask_question(office, text, language):
    """Record a question and the FAQ that best answers it, if any.

    Without `office`, it takes the office of the suggested FAQ.
    """
    match = find_best_match(text, office.code if office else None, language)
    if office is None and match is not None:
        office = match.faq.office
    return Inquiry.objects.create(
        office=office,
        text=text,
        language=language,
        matched_faq=match.faq if match else None,
        score=match.score if match else None,
        matched_by=match.matched_by if match else "",
    )


def resolve_inquiry(inquiry):
    """Record that the suggested answer resolved the question (US2c). Idempotent."""
    if inquiry.matched_faq_id is None:
        raise InquiryError(
            "No answer was suggested for this question, so none can resolve it."
        )
    if not inquiry.resolved:
        inquiry.resolved = True
        inquiry.save(update_fields=["resolved"])
    return inquiry
