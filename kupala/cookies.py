import dataclasses
import datetime
import email.utils
import typing

_NAME_FORBIDDEN = set(' \t,;()<>@:\\"/[]?={}')
_VALUE_FORBIDDEN = set(' \t,;"\\')


@dataclasses.dataclass
class Cookie:
    name: str
    value: str
    max_age: int | None = None
    expires: datetime.datetime | None = None
    domain: str | None = None
    path: str = "/"
    secure: bool = True
    httponly: bool = True
    samesite: typing.Literal["lax", "strict", "none"] | None = "lax"
    partitioned: bool = False

    def __post_init__(self) -> None:
        if not self.name or any(c in _NAME_FORBIDDEN or ord(c) < 32 for c in self.name):
            raise ValueError(f"Invalid cookie name: {self.name!r}")
        if any(c in _VALUE_FORBIDDEN or ord(c) < 32 for c in self.value):
            raise ValueError(f"Invalid cookie value: {self.value!r} (encode unsafe chars before passing)")
        if self.samesite == "none" and not self.secure:
            raise ValueError("SameSite=None cookies must be Secure")
        if self.partitioned and (self.samesite != "none" or not self.secure):
            raise ValueError("Partitioned cookies require SameSite=None and Secure")
        if any(c == ";" or ord(c) < 32 for c in self.path):
            raise ValueError(f"Invalid cookie path: {self.path!r}")
        if self.domain and any(c == ";" or ord(c) < 32 for c in self.domain):
            raise ValueError(f"Invalid cookie domain: {self.domain!r}")

    def __str__(self) -> str:
        parts = [f"{self.name}={self.value}"]
        if self.max_age is not None:
            parts.append(f"Max-Age={self.max_age}")

        if self.expires is not None:
            if self.expires.tzinfo is None:
                dt = self.expires.replace(tzinfo=datetime.UTC)
            else:
                dt = self.expires.astimezone(datetime.UTC)
            formatted = email.utils.format_datetime(dt, usegmt=True)
            parts.append(f"Expires={formatted}")

        if self.domain:
            parts.append(f"Domain={self.domain}")

        if self.path:
            parts.append(f"Path={self.path}")

        if self.secure:
            parts.append("Secure")

        if self.httponly:
            parts.append("HttpOnly")

        if self.samesite:
            parts.append(f"SameSite={self.samesite.capitalize()}")

        if self.partitioned:
            parts.append("Partitioned")

        return "; ".join(parts)

    @classmethod
    def delete(cls, name: str, *, path: str = "/", domain: str | None = None) -> typing.Self:
        """Build a cookie that instructs the browser to delete the named cookie."""
        return cls(
            name=name,
            value="",
            max_age=0,
            expires=datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC),
            path=path,
            domain=domain,
            secure=False,
            httponly=False,
            samesite="lax",
        )

    @classmethod
    def session(
        cls,
        name: str,
        value: str,
        *,
        path: str = "/",
        samesite: typing.Literal["lax", "strict", "none"] = "lax",
    ) -> typing.Self:
        """Build a session cookie: Secure, HttpOnly, no explicit expiration.

        Lifetime matches the browser session; sent only over HTTPS; unreadable
        from JavaScript.
        """
        return cls(
            name=name,
            value=value,
            path=path,
            secure=True,
            httponly=True,
            samesite=samesite,
        )

    @classmethod
    def cross_site(cls, name: str, value: str, *, partitioned: bool = False) -> typing.Self:
        """Build a cross-site cookie: SameSite=None, Secure, optionally Partitioned.

        For third-party embeds and SDKs. Pass ``partitioned=True`` to opt into
        CHIPS partitioning so the cookie is scoped per top-level site.
        """
        return cls(
            name=name,
            value=value,
            secure=True,
            samesite="none",
            partitioned=partitioned,
        )

    @classmethod
    def expires_at(
        cls,
        name: str,
        value: str,
        when: datetime.datetime,
        **kwargs: typing.Any,
    ) -> typing.Self:
        """Build a cookie that expires at a specific datetime.

        Extra keyword arguments are forwarded to the dataclass constructor.
        """
        return cls(name=name, value=value, expires=when, **kwargs)

    @classmethod
    def from_header(cls, header_value: str) -> typing.Self:
        """Parse a Set-Cookie header value into a Cookie.

        Attribute names are matched case-insensitively. Flags absent from the
        header end up as ``False``; ``Path`` defaults to "" (no attribute)
        rather than the constructor default so the round-trip preserves what
        was on the wire.
        """
        parts = [p.strip() for p in header_value.split(";") if p.strip()]
        if not parts or "=" not in parts[0]:
            raise ValueError(f"Invalid Set-Cookie header: {header_value!r}")

        name, _, value = parts[0].partition("=")
        name = name.strip()
        value = value.strip()

        kwargs: dict[str, typing.Any] = {
            "secure": False,
            "httponly": False,
            "samesite": None,
            "partitioned": False,
            "path": "",
        }
        for part in parts[1:]:
            attr, _, val = part.partition("=")
            attr_lower = attr.strip().lower()
            val = val.strip()
            match attr_lower:
                case "max-age":
                    kwargs["max_age"] = int(val)
                case "expires":
                    kwargs["expires"] = email.utils.parsedate_to_datetime(val)
                case "domain":
                    kwargs["domain"] = val
                case "path":
                    kwargs["path"] = val
                case "secure":
                    kwargs["secure"] = True
                case "httponly":
                    kwargs["httponly"] = True
                case "samesite":
                    kwargs["samesite"] = val.lower()
                case "partitioned":
                    kwargs["partitioned"] = True

        return cls(name=name, value=value, **kwargs)
