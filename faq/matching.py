"""Finding the published FAQ that best answers a student's question (FR7).

Two layers, so that another way of scoring can be added later without touching
the rest. A *matcher* answers one narrow question — which FAQ among these
candidates is the best answer, if any is relevant enough — with its own notion
of score and threshold. `find_best_match` holds the policy on top: the office
the student chose first, every office after.

The only matcher today is PostgreSQL full-text search. Semantic search over
embeddings (Chroma, IR4) is the planned second one; it would implement the same
`Matcher` protocol and be passed to `find_best_match`.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models import QuerySet

from .models import Faq

# The PostgreSQL text search configuration for each language the FAQs are
# written in: it decides the stemmer and the stop words.
SEARCH_CONFIGS = {"it": "italian", "en": "english"}

WORD = re.compile(r"\w+")


class MatchingUnavailable(ImproperlyConfigured):
    """The database cannot run the search: it is not PostgreSQL."""


@dataclass(frozen=True)
class Match:
    """A FAQ suggested as the answer to a question, and how relevant it is."""

    faq: Faq
    score: float

    @property
    def office_code(self):
        """The office the answer belongs to, which may not be the one asked."""
        return self.faq.office_code


class Matcher(Protocol):
    def best_match(
        self, question: str, language: str, candidates: QuerySet
    ) -> Match | None:
        """The candidate that best answers `question`, if relevant enough."""
        ...


class FullTextMatcher:
    """Ranks FAQs with PostgreSQL full-text search.

    The question is stemmed and stripped of stop words with the configuration
    of its language, then compared with the FAQ's text in that same language:
    its question weighted A, its answer B, so a word the FAQ is *about* counts
    more than one its answer happens to mention.

    The words of the question are OR-ed rather than AND-ed. A student writes a
    sentence, not a query, and requiring every word ("vorrei", "sapere", ...)
    would leave almost every question without a match. `ts_rank` averages over
    the words of the query, so a FAQ scores by the share of the question it
    covers, and scores stay comparable between short and long questions;
    ``FAQ_MATCH_MIN_RANK`` is the share below which a FAQ is not suggested.

    The vectors are computed on the fly rather than stored and indexed: the
    knowledge base is a few hundred rows per language at most, and a GIN index
    would only pay for itself well beyond that.
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
        # websearch never raises on malformed input, and the question has been
        # reduced to bare words anyway: "or" is the only operator it sees.
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
        return Match(faq=best, score=best.score)


def find_best_match(question, office_code, language, matcher=None):
    """The published FAQ that best answers `question`, or None.

    The office the student chose is searched first. Only if nothing there is
    relevant enough are all the offices searched, so a student who picked the
    wrong office still gets an answer, and the match tells them whose it is.
    """
    matcher = matcher or FullTextMatcher()
    published = Faq.objects.filter(is_active=True)
    return matcher.best_match(
        question, language, published.filter(office_code=office_code)
    ) or matcher.best_match(question, language, published)
