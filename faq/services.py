"""Asking a question and closing it (US2a-US2c).

Views never create or change an `Inquiry` themselves: they go through here, so
the rule that only a suggested answer can resolve a question lives in one
place.
"""

from .matching import find_best_match
from .models import Inquiry


class InquiryError(Exception):
    """A request about an inquiry that cannot be honoured."""


def ask_question(office_code, text, language):
    """Record a student's question and the FAQ that best answers it, if any.

    The search runs before anything is written, so a database that cannot
    search (see `MatchingUnavailable`) leaves no half-recorded question behind.
    """
    match = find_best_match(text, office_code, language)
    return Inquiry.objects.create(
        office_code=office_code,
        text=text,
        language=language,
        matched_faq=match.faq if match else None,
        score=match.score if match else None,
        matched_by=match.matched_by if match else "",
    )


def resolve_inquiry(inquiry):
    """Record that the suggested answer resolved the question (US2c).

    Idempotent: resolving twice is the same fact stated twice, and a client
    retrying after a lost response should not be told off for it.
    """
    if inquiry.matched_faq_id is None:
        raise InquiryError(
            "No answer was suggested for this question, so none can resolve it."
        )
    if not inquiry.resolved:
        inquiry.resolved = True
        inquiry.save(update_fields=["resolved"])
    return inquiry
