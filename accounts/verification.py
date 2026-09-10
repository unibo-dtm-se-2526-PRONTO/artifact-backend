"""Email verification: a signed link that activates a freshly registered account.

The token comes from Django's ``default_token_generator``, the same one used for
password resets: it needs no extra model field, and it is derived from the user's
password hash and last login, so it stops working once either changes.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

User = get_user_model()


def verification_url(user):
    """The absolute link a user has to open to activate their account."""
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.BACKEND_BASE_URL}/api/auth/verify/{uidb64}/{token}/"


def send_verification_email(user):
    send_mail(
        subject="Confirm your Pronto account",
        message=(
            "Welcome to Pronto.\n\n"
            "Open the link below to confirm this address and activate your "
            f"account:\n\n{verification_url(user)}\n\n"
            "If you did not sign up, ignore this message."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def activate(uidb64, token):
    """Activate the user the link points to. Returns None if the link is invalid."""
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    if not default_token_generator.check_token(user, token):
        return None
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    return user
