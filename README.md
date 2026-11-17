# http-cache-directive-lib

Parse a `Cache-Control` header into a structured dictionary of directives with their parameters.

```python
from http_cache_directive_lib import parse_cache_control

cc = parse_cache_control('private="Set-Cookie, Authorization", max-age=60, public')

cc.has("max-age")            # True
cc.get("max-age").value      # '60'
cc.get("private").value      # 'Set-Cookie, Authorization'
cc.get("private").quoted     # True
[d.name for d in cc.order]   # ['private', 'max-age', 'public']
cc.get_all("no-cache")       # []
```

The exported names are `parse_cache_control`, `CacheControl`, and `Directive`.

## Why this exists

Splitting a `Cache-Control` header on commas is the obvious approach and it is wrong: `private="Set-Cookie, Authorization"` contains a comma that is part of the value. This library scans the header with quote awareness, so quoted strings survive intact while still allowing the trailing comma that real servers send.

The trade-off is that parsing is lenient rather than strict. A malformed element is skipped instead of raising, and an empty value such as `foo=` is reported as `None` rather than as an empty string. A request handler that receives a broken header should keep serving, and callers almost never want to distinguish `foo=` from `foo`.

## The awkward edge

Directive names are lower-cased, but values are not. `MAX-AGE=60` and `max-age=60` are the same directive; `private="Set-Cookie"` is not the same value as `private="set-cookie"`, and this library does not try to make them so. When the same directive appears more than once, `get` returns the first occurrence and `get_all` returns every occurrence in header order.
