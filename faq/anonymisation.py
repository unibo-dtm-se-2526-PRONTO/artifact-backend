"""Remove personal data from helpdesk text before it is stored (NFR4).

========================  ================
what                      placeholder
========================  ================
e-mail addresses          ``[EMAIL]``
phone numbers             ``[PHONE]``
student ID numbers        ``[STUDENT_ID]``
Italian tax codes         ``[TAX_CODE]``
person names              ``[NAME]``
========================  ================

``@unibo.it`` addresses (office mailboxes) and links are kept. Names are
recognised only after a cue: an honorific, a self-introduction or a sign-off.
Applying it twice changes nothing more.
"""

import re

INSTITUTIONAL_EMAIL_DOMAIN = "unibo.it"

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")

# Codice fiscale: six letters, two digits, a letter, two digits, a letter,
# three digits and a check letter.
_TAX_CODE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)

# A number introduced as a matricola; the cue is kept.
_STUDENT_ID_WITH_CUE = re.compile(
    r"(?P<cue>\b(?:matricola|matr\.|student\s+(?:id|number)|id\s+number)"
    r"(?:\s*(?:is|è|n\.|nr\.|no\.|number)?)?\s*[:.#]?\s*)"
    r"(?<!\d)\d{5,10}(?!\d)",
    re.IGNORECASE,
)

# Current matricole (ten digits starting with 00) need no cue.
_STUDENT_ID = re.compile(r"(?<!\d)00\d{8}(?!\d)")

# Italian mobiles (3...) and landlines (0 then non-zero), optional +39/0039.
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


# No "Ing.": here it usually means "Ingegneria".
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
    # Order matters: matricole with a cue, phones, then bare matricole.
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
    # Without a prefix, at least nine digits, so dates are not taken.
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
