"""The vector store behind semantic FAQ matching (IR4).

Chroma keeps one entry per published FAQ and language: the embedding of the
FAQ's question in that language, with the FAQ's id and the language as
metadata. The question alone, not the answer: students ask questions, and a
paraphrase of a question sits closer to it than to the paragraph that answers
it. The entries are derived from the database and never edited by hand, so
they can be rebuilt at any time (`rebuild_faq_index`).

The embeddings are computed here, with fastembed, and handed to Chroma ready
made: Chroma stores and searches vectors, it never embeds anything itself. The
model is loaded once per process, on the first text that needs it.

Semantic matching is optional. With ``CHROMA_HOST`` empty, `get_collection`
returns None and every function here does nothing; when the server cannot be
reached, the calls raise and their callers (the signals and the matcher) log
the error and carry on without it.
"""

from functools import cache

from django.conf import settings

from .models import Faq

COLLECTION = "faqs"
LANGUAGES = ("it", "en")


@cache
def _client(host, port):
    import chromadb

    return chromadb.HttpClient(host=host, port=port)


def get_collection():
    """The Chroma collection of FAQ embeddings, or None when semantic
    matching is off."""
    if not settings.CHROMA_HOST:
        return None
    return _client(settings.CHROMA_HOST, settings.CHROMA_PORT).get_or_create_collection(
        COLLECTION,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )


@cache
def _model(name):
    from fastembed import TextEmbedding

    return TextEmbedding(name)


def embed(texts):
    """One embedding, as a list of floats, per text."""
    return [
        vector.tolist() for vector in _model(settings.FAQ_EMBEDDING_MODEL).embed(texts)
    ]


def entry_ids(faq_id):
    return [f"{faq_id}-{language}" for language in LANGUAGES]


def _add(collection, faqs):
    entries = [(faq, language) for faq in faqs for language in LANGUAGES]
    if not entries:
        return
    texts = [getattr(faq, f"question_{language}") for faq, language in entries]
    collection.upsert(
        ids=[f"{faq.pk}-{language}" for faq, language in entries],
        embeddings=embed(texts),
        metadatas=[
            {"faq_id": faq.pk, "language": language} for faq, language in entries
        ],
        documents=texts,
    )


def sync_faq(faq_id):
    """Bring the entries of one FAQ in line with the database: written if the
    FAQ is published, removed if it is not, or no longer exists."""
    collection = get_collection()
    if collection is None:
        return
    faq = Faq.objects.filter(pk=faq_id, is_active=True).first()
    if faq is None:
        collection.delete(ids=entry_ids(faq_id))
    else:
        _add(collection, [faq])


def rebuild():
    """Index every published FAQ again, dropping whatever else is stored.
    Returns how many FAQs were indexed.

    The new entries are written before the old ones are dropped, so a failure
    halfway (the model cannot be downloaded, say) leaves the store as it was
    rather than empty."""
    collection = get_collection()
    if collection is None:
        return 0
    faqs = list(Faq.objects.filter(is_active=True))
    _add(collection, faqs)
    current = {entry for faq in faqs for entry in entry_ids(faq.pk)}
    stale = [
        entry for entry in collection.get(include=[])["ids"] if entry not in current
    ]
    if stale:
        collection.delete(ids=stale)
    return len(faqs)


def nearest(question, language, faq_ids):
    """The FAQ among `faq_ids` whose question in `language` is closest to
    `question`, as ``(faq_id, cosine similarity)``; None if there is none."""
    collection = get_collection()
    if collection is None or not faq_ids:
        return None
    result = collection.query(
        query_embeddings=embed([question]),
        n_results=1,
        where={"$and": [{"language": language}, {"faq_id": {"$in": list(faq_ids)}}]},
        include=["distances", "metadatas"],
    )
    if not result["ids"][0]:
        return None
    # Chroma reports the cosine distance, 1 - similarity.
    return result["metadatas"][0][0]["faq_id"], 1 - result["distances"][0][0]
