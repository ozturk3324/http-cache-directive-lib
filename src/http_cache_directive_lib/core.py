"""Parse HTTP Cache-Control headers into structured directives.

A Cache-Control header is a comma-separated list of directives. A directive is
an optional token with an optional value, separated by ``=``. Values may be
tokens or quoted strings. This module keeps the parsed representation faithful
to the wire format: values are stored as the string that appeared after the
``=``, with surrounding quotes removed for quoted strings.

The parser is deliberately lenient about whitespace and empty list elements,
because real-world headers frequently contain ``Cache-Control: no-cache,``
with a trailing comma, or ``max-age = 60`` with spaces around the equals sign.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = ["Directive", "CacheControl", "parse_cache_control"]


@dataclass(frozen=True)
class Directive:
    """A single Cache-Control directive.

    ``name`` is the lower-cased directive name. ``value`` is ``None`` when the
    directive has no ``=`` part, otherwise it is the value with any surrounding
    double quotes removed. ``quoted`` records whether the original value was a
    quoted string, which callers occasionally need to distinguish from a token
    that happens to contain the same characters.
    """

    name: str
    value: Optional[str] = None
    quoted: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("directive name must not be empty")


@dataclass
class CacheControl:
    """The parsed form of a Cache-Control header.

    ``directives`` maps lower-cased directive names to a list of directives,
    because the same directive may legally appear more than once (for example
    ``no-cache`` and ``no-cache="Set-Cookie"``). ``order`` preserves the order
    in which directives appeared, which matters when a caller wants to
    reproduce the header or resolve duplicates by first-wins semantics.
    """

    directives: Dict[str, List[Directive]] = field(default_factory=dict)
    order: List[Directive] = field(default_factory=list)

    def get(self, name: str) -> Optional[Directive]:
        """Return the first directive with ``name``, or ``None``.

        First-wins is chosen because it is the least surprising rule for a
        header that is read left to right, and it is the rule HTTP/1.1 uses
        when a field is repeated.
        """

        values = self.directives.get(name.lower())
        if not values:
            return None
        return values[0]

    def get_all(self, name: str) -> List[Directive]:
        """Return every directive with ``name`` in header order."""

        return list(self.directives.get(name.lower(), ()))

    def has(self, name: str) -> bool:
        """Return ``True`` if at least one directive with ``name`` is present."""

        return name.lower() in self.directives

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return self.has(name)


# Characters that end a token per RFC 7230. A comma always ends a directive,
# but a comma inside a quoted string must not, so the scanner tracks quotes.
_TOKEN_DELIMITERS = set('(),/:;<=>?@[\\]{}')


def _is_token_char(ch: str) -> bool:
    if ch.isspace() or ch in _TOKEN_DELIMITERS:
        return False
    # Control characters and non-ASCII bytes are not valid token characters.
    return 0x21 <= ord(ch) <= 0x7E


def _split_directives(header: str) -> List[str]:
    """Split a Cache-Control header on commas outside quoted strings.

    A naive ``header.split(',')`` breaks on ``private="a,b"``. This scanner
    keeps quote state so quoted commas stay inside their directive.
    """

    parts: List[str] = []
    current: List[str] = []
    in_quotes = False
    escaped = False

    for ch in header:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if in_quotes and ch == "\\":
            current.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_quotes = not in_quotes
            current.append(ch)
            continue
        if ch == "," and not in_quotes:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)

    parts.append("".join(current))
    return parts


def _parse_value(raw: str) -> tuple[Optional[str], bool]:
    """Parse the value portion of a directive.

    Returns ``(value, quoted)``. An empty value (``foo=``) is treated as
    ``None`` because there is no meaningful value to expose; this matches the
    practical reading of a malformed header rather than inventing an empty
    string that callers would have to special-case.
    """

    raw = raw.strip()
    if not raw:
        return None, False
    if raw.startswith('"'):
        if len(raw) >= 2 and raw.endswith('"'):
            inner = raw[1:-1]
        else:
            # Unterminated quote: take the rest as the value, unquoted, so a
            # truncated header still yields something usable.
            inner = raw[1:]
        return _unescape_quoted(inner), True
    return raw, False


def _unescape_quoted(text: str) -> str:
    """Remove backslash escapes from a quoted-string value.

    RFC 7230 quoted-pair allows ``\\`` before any character. We drop the
    backslash and keep the following character, which is what a consumer of
    the value expects to see.
    """

    out: List[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _parse_directive(part: str) -> Optional[Directive]:
    """Parse one comma-separated element into a :class:`Directive`.

    Returns ``None`` for an empty element, which lets the caller skip the
    trailing comma that shows up in the wild.
    """

    part = part.strip()
    if not part:
        return None

    eq = part.find("=")
    if eq == -1:
        name = part.strip()
        if not name:
            return None
        return Directive(name=name.lower())

    name = part[:eq].strip()
    if not name:
        return None
    value, quoted = _parse_value(part[eq + 1 :])
    return Directive(name=name.lower(), value=value, quoted=quoted)


def parse_cache_control(header: str) -> CacheControl:
    """Parse a Cache-Control header value.

    ``header`` is the raw field value, without the field name. The return value
    is a :class:`CacheControl` that preserves order and keeps every occurrence
    of a repeated directive. Directive names are lower-cased so lookups are
    case-insensitive, matching HTTP's case-insensitive field semantics.

    Empty input yields an empty :class:`CacheControl`. Invalid elements are
    skipped rather than raising, because a malformed Cache-Control header must
    not take down a request handler.
    """

    result = CacheControl()
    if header is None:
        return result

    for raw_part in _split_directives(header):
        directive = _parse_directive(raw_part)
        if directive is None:
            continue
        result.directives.setdefault(directive.name, []).append(directive)
        result.order.append(directive)
    return result
