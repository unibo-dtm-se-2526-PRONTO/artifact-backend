"""Finding the published FAQ that best answers a student's question (FR7).

Two layers, so that another way of scoring can be added later without touching
the rest. A *matcher* answers one narrow question — which FAQ among these
candidates is the best answer, if any is relevant enough — with its own notion
of score and threshold. `find_best_match` holds the policy on top: the office
the student chose first, every office after.

There are two matchers, tried in cascade (`CascadeMatcher`). PostgreSQL
full-text search goes first: it is exact about the words the FAQs use (office
names, portals, acronyms such as ER.GO). Only when it finds nothing relevant
enough is semantic search over embeddings asked (Chroma, IR4), which finds a
FAQ worded differently from the question. Each keeps its own score and
threshold, which are never compared: a match says which matcher found it.
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
        return Match(faq=best, score=best.score, matched_by=MatchMethod.FULL_TEXT)


class SemanticMatcher:
    """Ranks FAQs by the cosine similarity between the embedding of the
    question and that of each FAQ's question, in the same language (see
    `faq.vector_index`). ``FAQ_SEMANTIC_MIN_SIMILARITY`` is the similarity
    below which a FAQ is not suggested.

    The search is restricted to the candidates' ids, so the database still
    decides what may be suggested: a FAQ unpublished while the vector store
    was down is not suggested even if its entries are still there.

    Semantic matching is an extra: with it off, or its store unreachable, this
    matcher finds nothing, and the error is logged rather than raised, so the
    student still gets the full-text answer, or the way to book.
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


def find_best_match(question, office_code, language, matcher=None):
    """The published FAQ that best answers `question`, or None.

    The office the student chose is searched first. Only if nothing there is
    relevant enough are all the offices searched, so a student who picked the
    wrong office still gets an answer, and the match tells them whose it is.
    The cascade runs whole in each step: a FAQ of the chosen office found by
    semantic search wins over a full-text match in another office.
    """
    matcher = matcher or CascadeMatcher(FullTextMatcher(), SemanticMatcher())
    # The office comes along with the FAQ: the answer is reported with it.
    published = Faq.objects.filter(is_active=True).select_related("office")
    return matcher.best_match(
        question, language, published.filter(office__code=office_code)
    ) or matcher.best_match(question, language, published)
