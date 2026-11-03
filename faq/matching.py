"""Find the published FAQ that best answers a question (FR7).

Full-text search first; semantic search (Chroma, IR4) only if it finds
nothing. Their scores are never compared.
"""

import logging
import re
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models import QuerySet

from . import vector_index
from .models import Faq, MatchMethod

logger = logging.getLogger(__name__)

SEARCH_CONFIGS = {"it": "italian", "en": "english"}

WORD = re.compile(r"\w+")


class MatchingUnavailable(ImproperlyConfigured):
    """The database cannot run the search: it is not PostgreSQL."""


@dataclass(frozen=True)
class Match:
    """A FAQ suggested as the answer to a question, and how relevant it is."""

    faq: Faq
    score: float
    matched_by: MatchMethod

    @property
    def office_code(self):
        """The office the answer belongs to, which may not be the one asked."""
        return self.faq.office.code


class Matcher(Protocol):
    def best_match(
        self, question: str, language: str, candidates: QuerySet
    ) -> Match | None:
        """The candidate that best answers `question`, if relevant enough."""
        ...


class FullTextMatcher:
    """Ranks FAQs with PostgreSQL full-text search.

    The FAQ question weighs more than the answer, and the words of the student's
    question are OR-ed, since it is a sentence, not a query.
    """

    def best_match(self, question, language, candidates):
        vendor = connections[candidates.db].vendor
        if vendor != "postgresql":
            raise MatchingUnavailable(
                f"FAQ matching needs PostgreSQL full-text search, not {vendor}."
            )
        config = SEARCH_CONFIGS[language]
        document = SearchVector(
            f"question_{language}", weight="A", config=config
        ) + SearchVector(f"answer_{language}", weight="B", config=config)
        query = SearchQuery(
            " or ".join(WORD.findall(question)),
            config=config,
            search_type="websearch",
        )
        best = (
            candidates.annotate(document=document, score=SearchRank(document, query))
            .filter(document=query, score__gte=settings.FAQ_MATCH_MIN_RANK)
            .order_by("-score", "pk")
            .first()
        )
        if best is None:
            return None
        return Match(faq=best, score=best.score, matched_by=MatchMethod.FULL_TEXT)


class SemanticMatcher:
    """Ranks FAQs by cosine similarity of the question embeddings.

    Limited to the candidates' ids. If the store is unreachable it logs the
    error and finds nothing.
    """

    def best_match(self, question, language, candidates):
        try:
            nearest = vector_index.nearest(
                question, language, candidates.values_list("pk", flat=True)
            )
        except Exception:
            logger.exception("Semantic FAQ search failed; using full-text only.")
            return None
        if nearest is None:
            return None
        faq_id, similarity = nearest
        if similarity < settings.FAQ_SEMANTIC_MIN_SIMILARITY:
            return None
        faq = candidates.filter(pk=faq_id).first()
        if faq is None:
            return None
        return Match(faq=faq, score=similarity, matched_by=MatchMethod.SEMANTIC)


class CascadeMatcher:
    """Asks each matcher in turn: the first one to find a match wins."""

    def __init__(self, *matchers: Matcher):
        self.matchers = matchers

    def best_match(self, question, language, candidates):
        for matcher in self.matchers:
            match = matcher.best_match(question, language, candidates)
            if match is not None:
                return match
        return None


def find_best_match(question, office_code, language):
    """The published FAQ that best answers `question`, or None.

    With `office_code`, that office is searched first, then all of them.
    """
    matcher = CascadeMatcher(FullTextMatcher(), SemanticMatcher())
    published = Faq.objects.filter(is_active=True).select_related("office")
    if office_code is None:
        return matcher.best_match(question, language, published)
    return matcher.best_match(
        question, language, published.filter(office__code=office_code)
    ) or matcher.best_match(question, language, published)
