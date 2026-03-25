import questionary
from utils.validator import validate_email


def _not_empty(value: str):
    """questionary validate callback — rejects blank input."""
    if not value or not value.strip():
        return "This field cannot be empty."
    return True


def ask_text(label: str, default: str = "", allow_empty: bool = False) -> str:
    """Plain text input. Strips result. Rejects empty unless allow_empty=True."""
    validate = None if allow_empty else _not_empty
    result = questionary.text(label, default=default, validate=validate).ask()
    return result.strip() if result else result


def ask_email(label: str, default: str = "", allow_empty: bool = False) -> str:
    """Text input that validates email format. allow_empty=True skips validation."""
    if allow_empty:
        result = questionary.text(label, default=default).ask()
        return result.strip() if result else result
    result = questionary.text(label, default=default, validate=validate_email).ask()
    return result.strip() if result else result


def ask_password(label: str) -> str:
    """Password input — never allows empty."""
    result = questionary.password(label, validate=_not_empty).ask()
    return result


def ask_autocomplete(label: str, choices: list, default: str = "",
                     allow_empty: bool = False) -> str:
    """Autocomplete with optional empty-check. Falls back to ask_text if no choices."""
    if not choices:
        return ask_text(label, default=default, allow_empty=allow_empty)
    validate = None if allow_empty else _not_empty
    result = questionary.autocomplete(
        label, choices=choices, default=default, validate=validate
    ).ask()
    return result.strip() if result else result


def ask_email_autocomplete(label: str, choices: list, default: str = "") -> str:
    """Autocomplete that also validates email format."""
    if not choices:
        return ask_email(label, default=default)
    result = questionary.autocomplete(
        label, choices=choices, default=default, validate=validate_email
    ).ask()
    return result.strip() if result else result
