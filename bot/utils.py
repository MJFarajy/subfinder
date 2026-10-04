"""Utility functions for domain normalization, validation, and formatting."""

import re
from typing import Optional, List, Tuple
from urllib.parse import urlparse

import idna

# Regex for validating domain names (RFC 1035, RFC 1123)
# Allows internationalized domain names in ASCII form (A-labels)
DOMAIN_REGEX = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)

# Regex to detect if input looks like a domain or URL
DOMAIN_LIKE_REGEX = re.compile(
    r"^(?:https?://)?(?:www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/.*)?$"
)


def normalize_domain(input_text: str) -> Optional[str]:
    """
    Normalize and extract root domain from user input.

    Handles:
    - Full URLs: https://www.example.com/path
    - URLs without scheme: www.example.com/path
    - Domains with www: www.example.com
    - Plain domains: example.com
    - Domains with port: example.com:8080
    - Internationalized domain names (IDN)

    Returns lowercase root domain or None if invalid.
    """
    if not input_text or not input_text.strip():
        return None

    text = input_text.strip().lower()

    # Remove scheme if present
    if "://" in text:
        try:
            parsed = urlparse(text)
            text = parsed.netloc or parsed.path
        except Exception:
            pass

    # Remove port if present
    if ":" in text and not text.startswith("["):  # Not IPv6
        text = text.split(":")[0]

    # Remove path/query/fragment
    text = text.split("/")[0].split("?")[0].split("#")[0]

    # Remove www. prefix
    if text.startswith("www."):
        text = text[4:]

    # Handle IDN domains (convert to ASCII/A-label form)
    try:
        text = idna.encode(text).decode("ascii")
    except Exception:
        # If IDNA encoding fails, keep as-is and let validation catch it
        pass

    # Final cleanup
    text = text.strip(".")

    if not text:
        return None

    return text if is_valid_domain(text) else None


def is_valid_domain(domain: str) -> bool:
    """
    Validate a domain name according to RFC 1035/1123.

    Args:
        domain: Domain name to validate (should already be normalized)

    Returns:
        True if valid, False otherwise
    """
    if not domain or len(domain) > 253:
        return False

    # Check overall format
    if not DOMAIN_REGEX.match(domain):
        return False

    # Each label must be 1-63 chars, not start/end with hyphen
    labels = domain.split(".")

    # Require at least 2 labels (e.g., example.com)
    if len(labels) < 2:
        return False

    for label in labels:
        if not label or len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False

    # TLD must be at least 2 chars (for practical purposes)
    if len(labels[-1]) < 2:
        return False

    return True


def looks_like_domain(text: str) -> bool:
    """Quick check if text looks like a domain or URL."""
    if not text:
        return False
    return bool(DOMAIN_LIKE_REGEX.match(text.strip()))


def format_subdomain_list(subdomains: List[str], max_message_length: int = 4000) -> Tuple[str, bool, List[str]]:
    """
    Format subdomain list for Telegram message.

    Returns:
        Tuple of (formatted_text, should_send_as_file, unique_subdomains_list)
    """
    if not subdomains:
        return "", False, []

    # Deduplicate, lowercase, sort
    unique_subs = sorted(set(s.lower().strip() for s in subdomains if s.strip()))

    return "", False, unique_subs


def extract_root_domain(domain: str) -> str:
    """
    Extract the root/apex domain (e.g., example.com from sub.example.com).
    This is a simple implementation - for production consider using tldextract.
    """
    parts = domain.lower().split(".")
    if len(parts) >= 2:
        # Simple heuristic: last two parts for most TLDs
        # This doesn't handle co.uk etc. perfectly but works for common cases
        return ".".join(parts[-2:])
    return domain