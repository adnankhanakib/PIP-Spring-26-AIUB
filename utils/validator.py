import re

EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_REGEX.match(value.strip()))


def validate_email(value: str):
    """Return error string for questionary, or True if valid."""
    if not value or not value.strip():
        return "Email address cannot be empty."
    if not is_valid_email(value):
        return "Enter a valid email address (e.g. user@example.com)."
    return True
