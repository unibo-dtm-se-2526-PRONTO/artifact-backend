"""Removing whatever could identify a requester from helpdesk text (NFR4).

The FAQ knowledge base is seeded from real questions students asked the phone
helpdesk, so before any of it is stored, ``anonymise`` replaces personal data
with neutral placeholders:

========================  ================
what                      placeholder
========================  ================
e-mail addresses          ``[EMAIL]``
phone numbers             ``[PHONE]``
student ID numbers        ``[STUDENT_ID]``
Italian tax codes         ``[TAX_CODE]``
person names              ``[NAME]``
========================  ================

Two deliberate exceptions keep the answers useful:

- addresses on the institutional domain ``@unibo.it`` stay. Students write
  from ``@studio.unibo.it`` (see ``accounts``), so an ``@unibo.it`` address
  belongs to the university — usually the office mailbox the answer points
  to — and never to the requester.
- links are left whole. They are the university's pages, and rewriting digits
  inside a path would only break them.

Phone numbers get no such exception: a student's number and an office's look
the same, and an office's number is published on its own page anyway.

Names are the heuristic part. Only a name announced by a cue is recognised:
an honorific (``Prof.``, ``dott.ssa``, ``Mr``...), a self-introduction
(``mi chiamo``, ``sono``, ``my name is``...) or a sign-off closing the text
(``Grazie, Mario Rossi``). A bare "Firstname Lastname" is not, because in this
data capitalised pairs are almost always degree courses ("Ingegneria
Biomedica"). After ``sono`` / ``I am`` two capitalised words are required for
the same reason, so "sono Mario" alone slips through: a first name on its own
is accepted as not identifying. What the patterns cannot see, a human reviews:
the importer leaves the FAQs unpublished by default.

Everything here is a pure function of the text, and applying it twice changes
nothing more, which the importer relies on to use the anonymised question as
its natural key.
"""

import re

INSTITUTIONAL_EMAIL_DOMAIN = "unibo.it"

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")

# Codice fiscale: six letters, two digits, a letter, two digits, a letter,
# three digits and a check letter.
_TAX_CODE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)

# A number, of any length a matricola has had, that the text itself says is
# one. The cue is kept: "matricola [STUDENT_ID]" still reads.
_STUDENT_ID_WITH_CUE = re.compile(
    r"(?P<cue>\b(?:matricola|matr\.|student\s+(?:id|number)|id\s+number)"
    r"(?:\s*(?:is|è|n\.|nr\.|no\.|number)?)?\s*[:.#]?\s*)"
    r"(?<!\d)\d{5,10}(?!\d)",
    re.IGNORECASE,
)

# Current Unibo matricole are ten digits with leading zeros ("0000912345"):
# distinctive enough to recognise without a cue. Shorter ones need the cue,
# or amounts and codes would go too.
_STUDENT_ID = re.compile(r"(?<!\d)00\d{8}(?!\d)")

# Italian numbers, optionally with the +39 / 0039 prefix: mobiles start with
# 3, landlines with 0 and a non-zero digit (so "00..." is left to the
# matricola below). Digits may be grouped by single spaces, dots or dashes,
# but never slashes or colons, so dates and times are not candidates.
_ITALIAN_PHONE = re.compile(
    r"(?<![\w+])(?P<prefix>(?:\+|00)39[ .-]?)?(?:3\d|0[1-9])(?:[ .-]?\d){4,9}(?!\d)"
)

# Any other number written in international format.
_INTERNATIONAL_PHONE = re.compile(r"(?<![\w+])\+\d{1,3}(?:[ .-]?\d){6,12}(?!\d)")

# A capitalised word, possibly with an elided particle or a hyphen:
# "Rossi", "D'Angelo", "Rossi-Bianchi".
_NAME_WORD = r"(?:[A-ZÀ-ÖØ-Þ]['’])?[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ]+(?:-[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ]+)?"


def _names(minimum):
    """``minimum`` to three capitalised words, on one line."""
    return rf"{_NAME_WORD}(?:[ \t]+{_NAME_WORD}){{{minimum - 1},2}}"


# "Ing." is left out on purpose: in this data it abbreviates "Ingegneria"
# ("Ing. Biomedica") far more often than it precedes an engineer's name.
_HONORIFIC_NAME = re.compile(
    r"(?P<cue>\b(?i:prof\.ssa|professoressa|professore|professor|prof\.?"
    r"|dott\.ssa|dottoressa|dottore|dott\.?|dr\.?"
    r"|sig\.ra|signora|signor|sig\.?|mrs\.?|mr\.?|ms\.?)[ \t]+)"
    rf"(?P<name>{_names(1)})"
)

_INTRODUCED_NAME = re.compile(
    r"(?P<cue>\b(?i:mi chiamo|il mio nome è|my name is)[ \t]+)"
    rf"(?P<name>{_names(1)})"
    r"|(?P<weak_cue>\b(?i:sono|i am|i['’]m)[ \t]+)"
    rf"(?P<weak_name>{_names(2)})"
)

_SIGNED_NAME = re.compile(
    r"(?P<cue>\b(?i:cordiali saluti|distinti saluti|saluti|cordialmente|grazie"
    r"|best regards|kind regards|regards|many thanks|thanks|thank you|best)"
    r"[ \t]*[,.!]?\s+)"
    rf"(?P<name>{_names(1)})"
    r"(?=[ \t]*[.!]?\s*$)"
)

# Capitalised words that follow a sign-off without being anyone's name.
_NOT_A_NAME = {"Mille", "Anticipatamente", "Ancora", "Tante", "Again", "Advance"}


def anonymise(text):
    """``text`` with personal data replaced by neutral placeholders."""
    # Links are cut out first and stitched back unchanged.
    pieces = []
    position = 0
    for link in _URL.finditer(text):
        pieces.append(_anonymise_prose(text[position : link.start()]))
        pieces.append(link.group(0))
        position = link.end()
    pieces.append(_anonymise_prose(text[position:]))
    return "".join(pieces)


def _anonymise_prose(text):
    text = _EMAIL.sub(_replace_email, text)
    text = _TAX_CODE.sub("[TAX_CODE]", text)
    # Student IDs with a cue go before phones, which could otherwise claim a
    # ten-digit matricola; bare matricole go after, since "0039..." is a phone.
    text = _STUDENT_ID_WITH_CUE.sub(r"\g<cue>[STUDENT_ID]", text)
    text = _ITALIAN_PHONE.sub(_replace_italian_phone, text)
    text = _INTERNATIONAL_PHONE.sub("[PHONE]", text)
    text = _STUDENT_ID.sub("[STUDENT_ID]", text)
    text = _HONORIFIC_NAME.sub(r"\g<cue>[NAME]", text)
    text = _INTRODUCED_NAME.sub(_replace_introduced_name, text)
    return _SIGNED_NAME.sub(_replace_signed_name, text)


def _replace_email(match):
    if match.group(1).lower() == INSTITUTIONAL_EMAIL_DOMAIN:
        return match.group(0)
    return "[EMAIL]"


def _replace_italian_phone(match):
    # The pattern only finds candidates; the length decides. Without a
    # prefix, nine digits at least: an eight-digit date such as 03.12.2024
    # starts with 0 too.
    digits = sum(ch.isdigit() for ch in match.group(0))
    if match.group("prefix"):
        digits -= 2 + (2 if match.group("prefix").startswith("00") else 0)
        shortest = 6
    else:
        shortest = 9
    if shortest <= digits <= 11:
        return "[PHONE]"
    return match.group(0)


def _replace_introduced_name(match):
    if match.group("cue") is not None:
        return f"{match.group('cue')}[NAME]"
    return f"{match.group('weak_cue')}[NAME]"


def _replace_signed_name(match):
    if match.group("name").split()[0] in _NOT_A_NAME:
        return match.group(0)
    return f"{match.group('cue')}[NAME]"
