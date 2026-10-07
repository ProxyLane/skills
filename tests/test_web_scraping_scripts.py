"""Offline tests for skills/web-scraping/scripts. Run: python3 -m unittest discover tests"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "web-scraping" / "scripts"))

import proxy_doctor  # noqa: E402
import verdict  # noqa: E402

ARTICLE = "<html><head><title>Shop</title></head><body><main>" + "Real product text. " * 30 + "</main></body></html>"


class VerdictTest(unittest.TestCase):
    def test_ok_page_with_enough_text(self):
        self.assertEqual(verdict.classify(200, ARTICLE).verdict, "ok")

    def test_transport_error_is_error(self):
        result = verdict.classify(None, None, error="ProxyError: 407")
        self.assertEqual((result.verdict, result.reason), ("error", "ProxyError: 407"))

    def test_cloudflare_interstitial_is_captcha_even_with_200(self):
        html = "<html><head><title>Just a moment...</title></head><body><script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'></script></body></html>"
        result = verdict.classify(200, html)
        self.assertEqual((result.verdict, result.vendor), ("captcha", "cloudflare"))

    def test_datadome_captcha(self):
        html = "<html><body><iframe src='https://geo.captcha-delivery.com/captcha/?initialCid=x'></iframe></body></html>"
        self.assertEqual(verdict.classify(403, html).vendor, "datadome")

    def test_google_sorry_redirect_url(self):
        result = verdict.classify(429, "<html></html>", url="https://www.google.com/sorry/index?continue=x")
        self.assertEqual((result.verdict, result.vendor), ("captcha", "google"))

    def test_google_javascript_wall_is_block(self):
        html = "<html><body><noscript><meta content=\"0;url=/httpservice/retry/enablejs?sei=x\" http-equiv=\"refresh\"></noscript>Please click here if you are not redirected</body></html>"
        result = verdict.classify(200, html, url="https://www.google.com/search?q=x")
        self.assertEqual((result.verdict, result.vendor), ("block", "google-js-wall"))

    def test_akamai_access_denied_is_block(self):
        html = "<html><head><title>Access Denied</title></head><body>You don't have permission. Reference&#32;#18.abc</body></html>"
        self.assertEqual(verdict.classify(403, html).verdict, "block")

    def test_bare_403_is_block(self):
        result = verdict.classify(403, "<html><body>nope</body></html>")
        self.assertEqual((result.verdict, result.reason), ("block", "HTTP 403"))

    def test_429_is_block(self):
        self.assertEqual(verdict.classify(429, ARTICLE).verdict, "block")

    def test_5xx_is_error(self):
        self.assertEqual(verdict.classify(502, ARTICLE).verdict, "error")

    def test_404_and_410_are_empty(self):
        self.assertEqual(verdict.classify(404, ARTICLE).verdict, "empty")
        self.assertEqual(verdict.classify(410, ARTICLE).verdict, "empty")

    def test_other_4xx_is_block(self):
        self.assertEqual(verdict.classify(400, ARTICLE).verdict, "block")

    def test_expect_is_literal_by_default(self):
        self.assertEqual(verdict.classify(200, "<p>Total: $10 (incl. tax)</p>", expect="$10 (incl.").verdict, "ok")

    def test_short_page_is_empty(self):
        self.assertEqual(verdict.classify(200, "<html><body><div id=app></div></body></html>").verdict, "empty")

    def test_script_text_does_not_count_as_content(self):
        html = "<html><body><script>" + "var x = 1;" * 500 + "</script></body></html>"
        self.assertEqual(verdict.classify(200, html).verdict, "empty")

    def test_expect_missing_is_empty(self):
        result = verdict.classify(200, ARTICLE, expect="Add to cart")
        self.assertEqual((result.verdict, result.reason), ("empty", "expected content missing"))

    def test_expect_present_short_page_is_ok(self):
        self.assertEqual(verdict.classify(200, "<p>Price: $10</p>", expect=r"Price: \$\d+", expect_regex=True).verdict, "ok")

    def test_page_mentioning_recaptcha_script_only_is_ok(self):
        html = ARTICLE.replace("</body>", "<script src='https://www.google.com/recaptcha/api.js'></script></body>")
        self.assertEqual(verdict.classify(200, html).verdict, "ok")

    def test_bytes_body(self):
        self.assertEqual(verdict.classify(200, ARTICLE.encode()).verdict, "ok")

    def test_cli_exit_code_and_json(self):
        out = io.StringIO()
        with mock.patch("sys.stdin", io.TextIOWrapper(io.BytesIO(b"<title>Just a moment...</title>"))), redirect_stdout(out):
            code = verdict.main(["-", "--status", "403"])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out.getvalue())["verdict"], "captcha")


def geo(ip, country="US", timezone="America/New_York"):
    return {"ok": True, "ip": ip, "country": country, "timezone": timezone, "latency_ms": 100}


class ProxyDoctorTest(unittest.TestCase):
    def test_redact_removes_decoded_and_short_credentials(self):
        for password in ("decoded%2Dsecret", "abc", "x"):
            with self.subTest(password=password):
                url = f"http://alice:{password}@gw.example:10000"
                decoded = proxy_doctor.unquote(password)
                message = proxy_doctor.redact(f"password={decoded}; via {url}", url)
                self.assertEqual(message, "password=***; via http://***@gw.example:10000")

    def test_http_check_refuses_environment_proxy_bypass(self):
        with mock.patch.dict(os.environ, {"NO_PROXY": "*", "no_proxy": "*"}), \
                mock.patch.object(proxy_doctor.urllib.request.HTTPHandler, "http_open") as direct:
            with self.assertRaises(proxy_doctor.ProxyBypassError):
                proxy_doctor.fetch_json("http://geo.example/json", "http://u:p@gw.example:10000", 1)
        direct.assert_not_called()

    def test_required_proxy_handler_checks_each_destination(self):
        handler = proxy_doctor.RequiredProxyHandler({"https": "http://u:p@gw.example:10000"})
        with mock.patch.object(proxy_doctor.urllib.request, "proxy_bypass", return_value=False):
            request = proxy_doctor.urllib.request.Request("https://geo.example/json")
            handler.proxy_open(request, "http://u:p@gw.example:10000", "https")
            self.assertEqual(request._tunnel_host, "geo.example")
            self.assertEqual(request.host, "gw.example:10000")
        with mock.patch.object(proxy_doctor.urllib.request, "proxy_bypass", return_value=True):
            redirected = proxy_doctor.urllib.request.Request("https://redirected.example/json")
            with self.assertRaises(proxy_doctor.ProxyBypassError):
                handler.proxy_open(redirected, "http://u:p@gw.example:10000", "https")

    def test_bypass_is_reported_without_a_successful_probe(self):
        with mock.patch.object(proxy_doctor, "fetch_json", side_effect=proxy_doctor.ProxyBypassError):
            result = proxy_doctor.probe("http://u:p@gw.example:10000", 1)
        self.assertFalse(result["ok"])
        self.assertIn("proxy bypass", result["error"])

    def test_exception_details_are_not_reported(self):
        for detail in ("decoded-secret", "abc", "session-token=private-value"):
            with self.subTest(detail=detail), \
                    mock.patch.object(proxy_doctor, "fetch_json", side_effect=RuntimeError(detail)):
                result = proxy_doctor.probe("http://alice:decoded%2Dsecret@gw.example:10000", 1)
                self.assertFalse(result["ok"])
                self.assertNotIn(detail, result["error"])
                self.assertEqual(result["error"], "RuntimeError: proxy check failed")

    def test_rejects_proxy_query_and_invalid_port_without_echoing_values(self):
        for url in ("http://alice:password@gw.example:secret-port",
                    "http://alice:password@gw.example:10000?token=private-value"):
            error = io.StringIO()
            with self.subTest(url=url), self.assertRaises(SystemExit), mock.patch("sys.stderr", error):
                proxy_doctor.main(["--proxy", url])
            self.assertNotIn("private-value", error.getvalue())
            self.assertNotIn("secret-port", error.getvalue())

    def test_redact_removes_credentials(self):
        url = "http://alice_c_US_s_abc:s3cret@gw.example:10000"
        message = proxy_doctor.redact(f"failed via {url}; user alice_c_US_s_abc pass s3cret", url)
        self.assertNotIn("s3cret", message)
        self.assertNotIn("alice", message)

    def test_session_placeholder(self):
        self.assertEqual(proxy_doctor.with_session("http://u_s_{session}:p@h:1", "ab12"), "http://u_s_ab12:p@h:1")

    def test_locale_fallback(self):
        self.assertEqual(proxy_doctor.locale_for("DE"), "de-DE")
        self.assertEqual(proxy_doctor.locale_for("ZZ"), "en-US")
        self.assertEqual(proxy_doctor.locale_for(None), "en-US")

    def test_normalize_ipinfo_and_ipwho(self):
        ipinfo = proxy_doctor.normalize_geo({"ip": "1.2.3.4", "country": "US", "city": "Lorton", "timezone": "America/New_York", "org": "AS701 Verizon"})
        ipwho = proxy_doctor.normalize_geo({"ip": "1.2.3.4", "country_code": "US", "timezone": {"id": "America/New_York"}, "connection": {"org": "Verizon"}})
        self.assertEqual((ipinfo["country"], ipinfo["timezone"]), ("US", "America/New_York"))
        self.assertEqual((ipwho["country"], ipwho["timezone"], ipwho["org"]), ("US", "America/New_York", "Verizon"))

    def test_stable_sticky_passes(self):
        summary = proxy_doctor.summarize([geo("1.1.1.1")] * 3, "US", sticky=True)
        self.assertEqual(summary["problems"], [])
        self.assertEqual(summary["browser"], {"timezone_id": "America/New_York", "locale": "en-US"})

    def test_sticky_ip_change_is_problem(self):
        summary = proxy_doctor.summarize([geo("1.1.1.1"), geo("2.2.2.2")], None, sticky=True)
        self.assertEqual(summary["ip_changes"], 1)
        self.assertTrue(any("sticky exit changed" in p for p in summary["problems"]))

    def test_rotating_change_is_note_not_problem(self):
        summary = proxy_doctor.summarize([geo("1.1.1.1", "RU", "Asia/Yekaterinburg"), geo("2.2.2.2", "GB", "Europe/London")], None, sticky=False)
        self.assertEqual(summary["problems"], [])
        self.assertEqual(len(summary["notes"]), 2)

    def test_country_mismatch(self):
        summary = proxy_doctor.summarize([geo("1.1.1.1", "DE", "Europe/Berlin")], "us", sticky=False)
        self.assertIn("exit country differs from US", summary["problems"])

    def test_unreachable(self):
        summary = proxy_doctor.summarize([{"ok": False, "error": "407", "latency_ms": 5}], None, sticky=False)
        self.assertFalse(summary["reachable"])
        self.assertIsNone(summary["browser"])

    def test_main_exit_codes_and_no_secret_in_output(self):
        out = io.StringIO()
        probes = iter([geo("1.1.1.1"), geo("2.2.2.2")])
        with mock.patch.object(proxy_doctor, "probe", side_effect=lambda *_: next(probes)), redirect_stdout(out):
            code = proxy_doctor.main(["--proxy", "http://bob_s_{session}:hunter2@gw.example:10000", "--probes", "2"])
        report = json.loads(out.getvalue())
        self.assertEqual(code, 2)  # {session} implies sticky, and the IP changed
        self.assertNotIn("hunter2", out.getvalue())
        self.assertEqual(len(report["session_id"]), 8)

    def test_407_stops_after_first_endpoint(self):
        error = proxy_doctor.urllib.error.HTTPError("https://ipinfo.io/json", 407, "Proxy Authentication Required", {}, None)
        with mock.patch.object(proxy_doctor, "fetch_json", side_effect=error) as fetch:
            result = proxy_doctor.probe("http://u:p@h:1", 1)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["error"], "HTTP 407 from proxy")

    def test_tunnel_407_from_urlerror_is_reported_as_proxy_auth(self):
        error = proxy_doctor.urllib.error.URLError("Tunnel connection failed: 407 Proxy Authentication Required")
        with mock.patch.object(proxy_doctor, "fetch_json", side_effect=error) as fetch:
            result = proxy_doctor.probe("http://user1:pass1@h:1", 1)
        self.assertEqual((fetch.call_count, result["error"]), (1, "HTTP 407 from proxy"))

    def test_session_argument_is_used(self):
        out = io.StringIO()
        with mock.patch.object(proxy_doctor, "probe", return_value=geo("1.1.1.1")) as probe, redirect_stdout(out):
            proxy_doctor.main(["--proxy", "http://bob_s_{session}:hunter2@gw.example:10000", "--probes", "1", "--session", "job01"])
        self.assertIn("bob_s_job01", probe.call_args.args[0])
        self.assertEqual(json.loads(out.getvalue())["session_id"], "job01")

    def test_browser_settings(self):
        with mock.patch.object(proxy_doctor, "probe", return_value=geo("1.1.1.1", "DE", "Europe/Berlin")):
            self.assertEqual(proxy_doctor.browser_settings("http://u:p@h:1"),
                             {"ip": "1.1.1.1", "country": "DE", "timezone_id": "Europe/Berlin", "locale": "de-DE"})
        with mock.patch.object(proxy_doctor, "probe", return_value={"ok": False, "error": "HTTP 407 from proxy"}):
            with self.assertRaises(RuntimeError):
                proxy_doctor.browser_settings("http://u:p@h:1")
        with mock.patch.object(proxy_doctor, "probe", return_value=geo("1.1.1.1", "DE", None)):
            with self.assertRaises(RuntimeError):
                proxy_doctor.browser_settings("http://u:p@h:1")

    def test_rejects_malformed_proxy(self):
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            proxy_doctor.main(["--proxy", "gw.example:10000"])


if __name__ == "__main__":
    unittest.main()
