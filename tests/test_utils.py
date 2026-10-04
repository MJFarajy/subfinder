"""Unit tests for domain normalization and validation utilities."""

import pytest

from bot.utils import (
    format_subdomain_list,
    is_valid_domain,
    looks_like_domain,
    normalize_domain,
)


class TestNormalizeDomain:
    """Tests for normalize_domain function."""

    def test_plain_domain(self):
        assert normalize_domain("example.com") == "example.com"

    def test_domain_with_www(self):
        assert normalize_domain("www.example.com") == "example.com"

    def test_domain_with_www_uppercase(self):
        assert normalize_domain("WWW.EXAMPLE.COM") == "example.com"

    def test_full_url_https(self):
        assert normalize_domain("https://example.com") == "example.com"

    def test_full_url_with_www_and_path(self):
        assert normalize_domain("https://www.example.com/path/to/page") == "example.com"

    def test_full_url_with_port(self):
        assert normalize_domain("https://example.com:8080") == "example.com"

    def test_url_without_scheme(self):
        assert normalize_domain("www.example.com/path") == "example.com"

    def test_domain_with_trailing_dot(self):
        assert normalize_domain("example.com.") == "example.com"

    def test_domain_with_leading_whitespace(self):
        assert normalize_domain("  example.com  ") == "example.com"

    def test_mixed_case(self):
        assert normalize_domain("ExAmPlE.CoM") == "example.com"

    def test_subdomain_extraction(self):
        # Should extract root domain
        assert normalize_domain("sub.example.com") == "sub.example.com"
        assert normalize_domain("api.sub.example.com") == "api.sub.example.com"

    def test_idn_domain(self):
        # IDN domains should be converted to ASCII
        # This is a simple test - actual conversion depends on idna library
        result = normalize_domain("مثال.ایران")
        assert result is not None
        assert isinstance(result, str)

    def test_invalid_domain_double_dot(self):
        assert normalize_domain("invalid..domain") is None

    def test_invalid_domain_starts_with_hyphen(self):
        assert normalize_domain("-example.com") is None

    def test_invalid_domain_ends_with_hyphen(self):
        assert normalize_domain("example-.com") is None

    def test_invalid_empty(self):
        assert normalize_domain("") is None
        assert normalize_domain("   ") is None
        assert normalize_domain(None) is None  # type: ignore

    def test_invalid_tld_too_short(self):
        assert normalize_domain("example.c") is None

    def test_invalid_label_too_long(self):
        long_label = "a" * 64
        assert normalize_domain(f"{long_label}.com") is None

    def test_domain_with_query_and_fragment(self):
        assert normalize_domain("https://example.com/path?query=1#fragment") == "example.com"


class TestIsValidDomain:
    """Tests for is_valid_domain function."""

    def test_valid_domains(self):
        valid = [
            "example.com",
            "sub.example.com",
            "a.b.c.d.example.com",
            "example.org",
            "example.net",
            "test-domain.com",
            "test123.com",
            "xn--mgbaam7a8h.xn--mgbayh7gpa",  # IDN in ASCII form
        ]
        for domain in valid:
            assert is_valid_domain(domain), f"Should be valid: {domain}"

    def test_invalid_domains(self):
        invalid = [
            "",
            ".com",
            "com",
            "example.",
            "example..com",
            "-example.com",
            "example-.com",
            "exa mple.com",  # space
            "example.c",  # TLD too short
            "a" * 64 + ".com",  # label too long
        ]
        for domain in invalid:
            assert not is_valid_domain(domain), f"Should be invalid: {domain}"

        # This is actually valid per RFC (TLD >= 2 chars)
        assert is_valid_domain("example.toolongtld")

    def test_max_length(self):
        # Max 253 chars total
        # 63 + 1 + 63 + 1 + 63 + 1 + 60 = 252 (valid)
        assert is_valid_domain("a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 60)
        # 63 + 1 + 63 + 1 + 63 + 1 + 61 = 253 (valid - at limit)
        assert is_valid_domain("a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 61)
        # 63 + 1 + 63 + 1 + 63 + 1 + 62 = 254 (invalid - over limit)
        assert not is_valid_domain("a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 62)


class TestLooksLikeDomain:
    """Tests for looks_like_domain function."""

    def test_positive_cases(self):
        positive = [
            "example.com",
            "www.example.com",
            "https://example.com",
            "http://www.example.com/path",
            "sub.domain.example.com",
            "example.org",
            "test-domain.com",
        ]
        for text in positive:
            assert looks_like_domain(text), f"Should look like domain: {text}"

    def test_negative_cases(self):
        negative = [
            "",
            "not a domain",
            "justtext",
            "example",
            "http://",
            "ftp://example.com",  # not http/https
            "example.",  # trailing dot without TLD
        ]
        for text in negative:
            assert not looks_like_domain(text), f"Should not look like domain: {text}"


class TestFormatSubdomainList:
    """Tests for format_subdomain_list function."""

    def test_empty_list(self):
        text, as_file, unique_subs = format_subdomain_list([])
        assert text == ""
        assert not as_file
        assert unique_subs == []

    def test_single_subdomain(self):
        text, as_file, unique_subs = format_subdomain_list(["sub.example.com"])
        assert text == ""
        assert not as_file
        assert unique_subs == ["sub.example.com"]

    def test_multiple_subdomains(self):
        subs = ["b.example.com", "a.example.com", "c.example.com"]
        text, as_file, unique_subs = format_subdomain_list(subs)
        assert text == ""
        assert not as_file
        assert unique_subs == ["a.example.com", "b.example.com", "c.example.com"]

    def test_deduplication(self):
        subs = ["a.example.com", "A.EXAMPLE.COM", "b.example.com", "a.example.com"]
        text, as_file, unique_subs = format_subdomain_list(subs)
        assert unique_subs == ["a.example.com", "b.example.com"]

    def test_whitespace_handling(self):
        subs = ["  a.example.com  ", "\tb.example.com\n", "c.example.com"]
        text, as_file, unique_subs = format_subdomain_list(subs)
        assert unique_subs == ["a.example.com", "b.example.com", "c.example.com"]

    def test_long_result_as_file(self):
        # Create a very long list
        subs = [f"sub{i}.example.com" for i in range(2000)]
        text, as_file, unique_subs = format_subdomain_list(subs, max_message_length=1000)
        # The function now returns empty text and lets the caller handle formatting
        assert text == ""
        assert not as_file
        assert len(unique_subs) == 2000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])