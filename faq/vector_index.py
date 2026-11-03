"""The Chroma vector store for semantic FAQ matching (IR4).

One entry per published FAQ and language: the embedding of its question,
computed here with fastembed. With ``CHROMA_HOST`` empty everything here is a
no-op. `rebuild_faq_index` rebuilds it from the database.
"""

from functools import cache

from django.conf import settings

from pronto.enums import Language

from .models import Faq

COLLECTION = "faqs"


@cache
def _client(host, port):
    import chromadb

    return chromadb.HttpClient(host=host, port=port)


def get_collection():
    """The Chroma collection, or None when semantic matching is off."""
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


def entry_id(faq_id, language):
    return f"{faq_id}-{language}"


def entry_ids(faq_id):
    return [entry_id(faq_id, language) for language in Language.values]


def _add(collection, faqs):
    entries = [(faq, language) for faq in faqs for language in Language.values]
    if not entries:
        return
    texts = [getattr(faq, f"question_{language}") for faq, language in entries]
    collection.upsert(
        ids=[entry_id(faq.pk, language) for faq, language in entries],
        embeddings=embed(texts),
        metadatas=[
            {"faq_id": faq.pk, "language": language} for faq, language in entries
        ],
        documents=texts,
    )


def sync_faq(faq_id):
    """Write the FAQ's entries if it is published, remove them otherwise."""
    collection = get_collection()
    if collection is None:
        return
    faq = Faq.objects.filter(pk=faq_id, is_active=True).first()
    if faq is None:
        collection.delete(ids=entry_ids(faq_id))
    else:
        _add(collection, [faq])


def rebuild():
    """Index every published FAQ again and drop the rest; returns the count.

    Writes before deleting, so a failure leaves the old index in place.
    """
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
    """``(faq_id, cosine similarity)`` of the closest FAQ in `faq_ids`, or None."""
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
