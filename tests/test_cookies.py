import datetime

import pytest

from kupala.cookies import Cookie

EXPIRES = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
EXPIRES_RFC1123 = "Thu, 01 Jan 2026 12:00:00 GMT"


class TestConstruction:
    def test_minimal_cookie(self) -> None:
        cookie = Cookie(name="sid", value="abc")
        assert cookie.name == "sid"
        assert cookie.value == "abc"

    def test_default_values(self) -> None:
        cookie = Cookie(name="sid", value="abc")
        assert cookie.max_age is None
        assert cookie.expires is None
        assert cookie.domain is None
        assert cookie.path == "/"
        assert cookie.secure is True
        assert cookie.httponly is True
        assert cookie.samesite == "lax"
        assert cookie.partitioned is False

    def test_all_attributes_set(self) -> None:
        cookie = Cookie(
            name="sid",
            value="abc",
            max_age=3600,
            expires=EXPIRES,
            domain="example.com",
            path="/api",
            secure=True,
            httponly=False,
            samesite="strict",
        )
        assert cookie.max_age == 3600
        assert cookie.expires == EXPIRES
        assert cookie.domain == "example.com"
        assert cookie.path == "/api"
        assert cookie.httponly is False
        assert cookie.samesite == "strict"


class TestValidation:
    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cookie name"):
            Cookie(name="", value="x")

    def test_name_with_separator_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cookie name"):
            Cookie(name="bad;name", value="x")

    def test_name_with_control_char_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cookie name"):
            Cookie(name="bad\nname", value="x")

    def test_value_with_separator_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cookie value"):
            Cookie(name="ok", value="bad;value")

    def test_value_with_crlf_raises(self) -> None:
        """CRLF injection attempt — must be rejected by the control-char check."""
        with pytest.raises(ValueError, match="Invalid cookie value"):
            Cookie(name="ok", value="bad\r\nSet-Cookie: evil=1")

    def test_empty_value_allowed(self) -> None:
        """Empty value is the canonical 'delete this cookie' pattern."""
        cookie = Cookie(name="ok", value="")
        assert cookie.value == ""

    def test_samesite_none_without_secure_raises(self) -> None:
        with pytest.raises(ValueError, match="SameSite=None cookies must be Secure"):
            Cookie(name="ok", value="x", samesite="none", secure=False)

    def test_partitioned_without_samesite_none_raises(self) -> None:
        with pytest.raises(ValueError, match="Partitioned cookies require"):
            Cookie(name="ok", value="x", partitioned=True, samesite="lax", secure=True)

    def test_path_with_semicolon_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cookie path"):
            Cookie(name="ok", value="x", path="/foo;Domain=evil")

    def test_path_with_control_char_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cookie path"):
            Cookie(name="ok", value="x", path="/foo\n")

    def test_domain_with_semicolon_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cookie domain"):
            Cookie(name="ok", value="x", domain="example.com;Path=/")


class TestFormatting:
    def test_default_cookie(self) -> None:
        cookie = Cookie(name="sid", value="abc")
        assert str(cookie) == "sid=abc; Path=/; Secure; HttpOnly; SameSite=Lax"

    def test_all_attributes_lax_variant(self) -> None:
        cookie = Cookie(
            name="sid",
            value="abc",
            max_age=3600,
            expires=EXPIRES,
            domain="example.com",
            path="/api",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        assert str(cookie) == (
            f"sid=abc; Max-Age=3600; Expires={EXPIRES_RFC1123}; "
            f"Domain=example.com; Path=/api; Secure; HttpOnly; SameSite=Lax"
        )

    def test_cross_site_variant_with_partitioned(self) -> None:
        cookie = Cookie(
            name="sid",
            value="abc",
            secure=True,
            httponly=True,
            samesite="none",
            partitioned=True,
        )
        assert str(cookie) == "sid=abc; Path=/; Secure; HttpOnly; SameSite=None; Partitioned"

    def test_naive_expires_treated_as_utc(self) -> None:
        naive = datetime.datetime(2026, 1, 1, 12, 0, 0)
        cookie = Cookie(name="ok", value="x", expires=naive)
        assert f"Expires={EXPIRES_RFC1123}" in str(cookie)

    def test_aware_non_utc_expires_converted(self) -> None:
        plus_one = datetime.timezone(datetime.timedelta(hours=1))
        aware = datetime.datetime(2026, 1, 1, 13, 0, 0, tzinfo=plus_one)
        cookie = Cookie(name="ok", value="x", expires=aware)
        assert f"Expires={EXPIRES_RFC1123}" in str(cookie)

    def test_empty_path_omitted(self) -> None:
        cookie = Cookie(name="ok", value="x", path="")
        assert "Path=" not in str(cookie)

    def test_samesite_python_none_omits_attribute(self) -> None:
        """Python None disables the SameSite attribute; the string "none" emits SameSite=None."""
        cookie = Cookie(name="ok", value="x", samesite=None)
        assert "SameSite" not in str(cookie)


class TestDelete:
    def test_produces_expiration_cookie(self) -> None:
        cookie = Cookie.delete("sid")
        assert cookie.value == ""
        assert cookie.max_age == 0
        assert cookie.expires == datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)

    def test_custom_path_and_domain(self) -> None:
        cookie = Cookie.delete("sid", path="/api", domain="example.com")
        assert cookie.path == "/api"
        assert cookie.domain == "example.com"

    def test_secure_false_for_http_compatibility(self) -> None:
        """Deletion cookies omit Secure so they work in HTTP contexts during dev/redirect chains."""
        cookie = Cookie.delete("sid")
        assert cookie.secure is False


class TestSession:
    def test_defaults_are_secure(self) -> None:
        cookie = Cookie.session("sid", "abc")
        assert cookie.secure is True
        assert cookie.httponly is True
        assert cookie.samesite == "lax"
        assert cookie.max_age is None
        assert cookie.expires is None

    def test_custom_samesite(self) -> None:
        cookie = Cookie.session("sid", "abc", samesite="strict")
        assert cookie.samesite == "strict"

    def test_custom_path(self) -> None:
        cookie = Cookie.session("sid", "abc", path="/api")
        assert cookie.path == "/api"


class TestCrossSite:
    def test_defaults(self) -> None:
        cookie = Cookie.cross_site("sid", "abc")
        assert cookie.samesite == "none"
        assert cookie.secure is True
        assert cookie.partitioned is False

    def test_partitioned_true(self) -> None:
        cookie = Cookie.cross_site("sid", "abc", partitioned=True)
        assert cookie.partitioned is True


class TestExpiresAt:
    def test_sets_expires(self) -> None:
        cookie = Cookie.expires_at("sid", "abc", EXPIRES)
        assert cookie.expires == EXPIRES

    def test_forwards_kwargs(self) -> None:
        cookie = Cookie.expires_at("sid", "abc", EXPIRES, max_age=60)
        assert cookie.max_age == 60


class TestFromHeader:
    def test_round_trip(self) -> None:
        original = Cookie(name="sid", value="abc", max_age=60)
        parsed = Cookie.from_header(str(original))
        assert parsed == original

    def test_parses_all_attributes(self) -> None:
        header = (
            f"sid=abc; Max-Age=3600; Expires={EXPIRES_RFC1123}; "
            "Domain=example.com; Path=/api; Secure; HttpOnly; SameSite=Lax"
        )
        cookie = Cookie.from_header(header)
        assert cookie.name == "sid"
        assert cookie.value == "abc"
        assert cookie.max_age == 3600
        assert cookie.expires == EXPIRES
        assert cookie.domain == "example.com"
        assert cookie.path == "/api"
        assert cookie.secure is True
        assert cookie.httponly is True
        assert cookie.samesite == "lax"

    def test_attribute_names_case_insensitive(self) -> None:
        header = "sid=abc; SECURE; HTTPONLY; SAMESITE=lax; PATH=/"
        cookie = Cookie.from_header(header)
        assert cookie.secure is True
        assert cookie.httponly is True
        assert cookie.samesite == "lax"
        assert cookie.path == "/"

    def test_whitespace_tolerated(self) -> None:
        cookie = Cookie.from_header("sid =  abc ;  Path = /api  ;  Secure")
        assert cookie.name == "sid"
        assert cookie.value == "abc"
        assert cookie.path == "/api"
        assert cookie.secure is True

    def test_multiple_path_last_wins(self) -> None:
        cookie = Cookie.from_header("sid=abc; Path=/; Path=/api")
        assert cookie.path == "/api"

    def test_flag_attributes_without_value(self) -> None:
        cookie = Cookie.from_header("sid=abc; Secure; HttpOnly")
        assert cookie.secure is True
        assert cookie.httponly is True

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Set-Cookie header"):
            Cookie.from_header("")

    def test_first_part_without_equals_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Set-Cookie header"):
            Cookie.from_header("no-equals-here; Path=/")
