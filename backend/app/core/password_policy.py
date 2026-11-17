"""Password policy validation and normalization aligned with NIST SP 800-63B.

Guidelines followed:
- Minimum length of 8 characters
- Maximum length of 128 characters (to allow long, memorable passphrases)
- Unicode NFKC normalization
- Disallow passwords consisting solely of whitespace
- Disallow single repeated characters (e.g. "aaaaaaaa", "11111111")
- Reject commonly breached and easily guessed trivial passwords
- No arbitrary composition rules (e.g. mandatory uppercase/digits/symbols) that harm
  passphrase usability and entropy.
"""
import unicodedata

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# Common trivial and easily guessed passwords (checked in lowercase/normalized form)
COMMON_PASSWORDS: frozenset[str] = frozenset({
    "password",
    "password123",
    "password1234",
    "12345678",
    "123456789",
    "1234567890",
    "qwertyuiop",
    "admin123",
    "admin1234",
    "letmein123",
    "welcome123",
    "passphrase",
    "iloveyou",
    "monkey123",
    "dragon123",
    "football",
    "master123",
    "sunshine",
    "princess",
    "charlie123",
    "shadow123",
})


def normalize_password(password: str) -> str:
    """Normalize password using Unicode NFKC normalization per NIST SP 800-63B."""
    if not isinstance(password, str):
        return ""
    return unicodedata.normalize("NFKC", password)


def validate_password_strength(password: str) -> tuple[bool, str | None]:
    """Validate password strength according to NIST SP 800-63B guidelines.

    Returns:
        tuple[bool, str | None]: (True, None) if password meets policy,
        or (False, error_message) describing why validation failed.
    """
    if not isinstance(password, str):
        return False, "Password must be a valid text string."

    normalized = normalize_password(password)

    if not normalized.strip():
        return False, "Password cannot consist solely of whitespace."

    if len(normalized) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."

    if len(normalized) > MAX_PASSWORD_LENGTH:
        return False, f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters."

    # Reject single repeated character strings (e.g. "aaaaaaaa", "11111111")
    if len(set(normalized)) <= 1:
        return False, "Password cannot consist of a single repeated character."

    # Check against common trivial passwords list
    cleaned_lower = normalized.strip().lower()
    if cleaned_lower in COMMON_PASSWORDS:
        return (
            False,
            "Password is too common or easily guessed. Please choose a stronger password or passphrase.",
        )

    return True, None
