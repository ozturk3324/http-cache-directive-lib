import unittest

from http_cache_directive_lib import CacheControl, Directive, parse_cache_control


class ParseCacheControlTests(unittest.TestCase):
    def test_single_valueless_directive(self):
        cc = parse_cache_control("no-cache")
        self.assertTrue(cc.has("no-cache"))
        self.assertEqual(cc.get("no-cache"), Directive(name="no-cache"))
        self.assertIsNone(cc.get("no-cache").value)
        self.assertFalse(cc.get("no-cache").quoted)

    def test_multiple_directives_preserve_order(self):
        cc = parse_cache_control("max-age=60, public, must-revalidate")
        self.assertEqual([d.name for d in cc.order], ["max-age", "public", "must-revalidate"])
        self.assertEqual(cc.get("max-age").value, "60")
        self.assertIsNone(cc.get("public").value)

    def test_whitespace_around_equals_and_commas(self):
        cc = parse_cache_control("  max-age = 300 ,  public  ")
        self.assertEqual(cc.get("max-age").value, "300")
        self.assertTrue(cc.has("public"))

    def test_directive_names_are_lowercased(self):
        cc = parse_cache_control("No-Cache, MAX-AGE=10")
        self.assertTrue(cc.has("no-cache"))
        self.assertTrue(cc.has("max-age"))
        self.assertTrue(cc.has("NO-CACHE"))
        self.assertEqual(cc.get("Max-Age").value, "10")

    def test_quoted_value_with_comma(self):
        cc = parse_cache_control('private="Set-Cookie, Authorization", max-age=0')
        directive = cc.get("private")
        self.assertEqual(directive.value, "Set-Cookie, Authorization")
        self.assertTrue(directive.quoted)
        self.assertEqual(cc.get("max-age").value, "0")

    def test_quoted_value_with_escaped_quote(self):
        cc = parse_cache_control('no-cache="a\\"b"')
        directive = cc.get("no-cache")
        self.assertEqual(directive.value, 'a"b')
        self.assertTrue(directive.quoted)

    def test_empty_value_becomes_none(self):
        cc = parse_cache_control("foo=")
        directive = cc.get("foo")
        self.assertIsNotNone(directive)
        self.assertIsNone(directive.value)
        self.assertFalse(directive.quoted)

    def test_trailing_and_leading_commas_are_skipped(self):
        cc = parse_cache_control(",max-age=5,,")
        self.assertEqual([d.name for d in cc.order], ["max-age"])
        self.assertEqual(cc.get("max-age").value, "5")

    def test_repeated_directive_keeps_all_occurrences(self):
        cc = parse_cache_control("no-cache, no-cache=\"Set-Cookie\"")
        all_no_cache = cc.get_all("no-cache")
        self.assertEqual(len(all_no_cache), 2)
        self.assertIsNone(all_no_cache[0].value)
        self.assertEqual(all_no_cache[1].value, "Set-Cookie")
        self.assertEqual(cc.get("no-cache"), all_no_cache[0])

    def test_empty_header_yields_empty_result(self):
        cc = parse_cache_control("")
        self.assertEqual(cc.order, [])
        self.assertEqual(cc.directives, {})
        self.assertFalse(cc.has("no-cache"))
        self.assertIsNone(cc.get("no-cache"))
        self.assertEqual(cc.get_all("no-cache"), [])

    def test_none_header_is_tolerated(self):
        cc = parse_cache_control(None)
        self.assertEqual(cc.order, [])

    def test_contains_operator(self):
        cc = parse_cache_control("public")
        self.assertIn("public", cc)
        self.assertIn("PUBLIC", cc)
        self.assertNotIn("private", cc)
        self.assertNotIn(123, cc)

    def test_unterminated_quote_still_yields_value(self):
        cc = parse_cache_control('private="Set-Cookie')
        directive = cc.get("private")
        self.assertEqual(directive.value, "Set-Cookie")
        self.assertTrue(directive.quoted)

    def test_returns_cache_control_instance(self):
        cc = parse_cache_control("public")
        self.assertIsInstance(cc, CacheControl)
        self.assertIsInstance(cc.get("public"), Directive)


if __name__ == "__main__":
    unittest.main()
