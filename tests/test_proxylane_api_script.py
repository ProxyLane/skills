"""Offline tests for skills/proxylane-api/scripts/proxylane.py. Run: python3 -m unittest discover tests"""

import io
import json
import os
import sys
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "proxylane-api" / "scripts"))

import proxylane  # noqa: E402

KEY = "plr_" + "a" * 40


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ProxyLaneApiScriptTest(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"PROXYLANE_API_KEY": KEY}, clear=False)
        self.env.start()
        self.requests = []

    def tearDown(self):
        self.env.stop()

    def opener(self, payload=b'{"data": {}}', error=None):
        def open_(request, timeout):
            self.requests.append(request)
            if error:
                raise error
            return FakeResponse(payload)
        return open_

    def run_command(self, argv, **opener):
        open_ = self.opener(**opener)
        args = proxylane.parser().parse_args(argv)
        return proxylane.run(args, call=lambda *a, **k: proxylane.call(*a, **k, opener=open_))

    def test_buy_sends_whole_gb_with_an_idempotency_key_and_bearer_key(self):
        self.run_command(["buy", "50"])
        request = self.requests[0]
        self.assertEqual((request.get_method(), request.full_url), ("POST", proxylane.DEFAULT_BASE_URL + "/traffic/purchase"))
        self.assertEqual(json.loads(request.data), {"gb": 50})
        self.assertEqual(request.get_header("Authorization"), "Bearer " + KEY)
        self.assertTrue(request.get_header("Idempotency-key"))

    def test_retry_reuses_the_given_idempotency_key(self):
        self.run_command(["--key", "retry-0001", "allocate", "abc", "2.5"])
        self.assertEqual(self.requests[0].get_header("Idempotency-key"), "retry-0001")
        self.assertEqual(json.loads(self.requests[0].data), {"gb": 2.5})

    def test_reclaim_without_amount_returns_everything(self):
        self.run_command(["reclaim", "abc"])
        self.assertEqual(json.loads(self.requests[0].data), {})
        self.assertTrue(self.requests[0].full_url.endswith("/subaccounts/abc/reclaim"))

    def test_reads_do_not_send_idempotency_keys(self):
        self.run_command(["list", "--search", "crm 1"])
        self.assertIsNone(self.requests[0].get_header("Idempotency-key"))
        self.assertTrue(self.requests[0].full_url.endswith("/subaccounts?search=crm+1"))

    def test_proxies_sends_only_given_targeting(self):
        self.run_command(["proxies", "abc", "--country", "US", "--count", "3"])
        self.assertEqual(json.loads(self.requests[0].data), {"session_mode": "sticky", "protocol": "socks5", "gateway": "europe", "count": 3, "format": "url", "country": "US"})

    def test_old_reseller_variables_still_work(self):
        with mock.patch.dict(os.environ, {"PROXYLANE_API_KEY": "", "PROXYLANE_RESELLER_KEY": KEY, "PROXYLANE_RESELLER_API": "https://example.test/api/reseller/v1"}):
            self.assertEqual(proxylane.api_key(), KEY)
            self.assertEqual(proxylane.base_url(), "https://example.test/api/reseller/v1")

    def test_http_error_becomes_an_api_error_with_its_details(self):
        body = io.BytesIO(json.dumps({"error": {"code": "insufficient_pool_traffic", "message": "Not enough", "available_bytes": 5}}).encode())
        error = urllib.error.HTTPError(proxylane.DEFAULT_BASE_URL, 409, "Conflict", {}, body)
        with self.assertRaises(proxylane.ApiError) as raised:
            self.run_command(["account"], error=error)
        self.assertEqual((raised.exception.status, raised.exception.code, raised.exception.details), (409, "insufficient_pool_traffic", {"available_bytes": 5}))

    def test_cli_prints_errors_to_stderr_without_the_key(self):
        failure = proxylane.ApiError(409, "insufficient_pool_traffic", "Not enough", {"available_bytes": 5})
        stderr = io.StringIO()
        with mock.patch.object(proxylane, "run", side_effect=failure), redirect_stderr(stderr):
            self.assertEqual(proxylane.main(["account"]), 1)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["available_bytes"], 5)
        self.assertNotIn(KEY, stderr.getvalue())

    def test_missing_key_stops_before_any_request(self):
        with mock.patch.dict(os.environ, {"PROXYLANE_API_KEY": "", "PROXYLANE_RESELLER_KEY": ""}):
            with self.assertRaises(SystemExit):
                self.run_command(["account"])
        self.assertEqual(self.requests, [])

    def test_successful_output_is_json(self):
        with mock.patch.object(proxylane, "run", return_value={"data": {"pool_gb": 1}}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(proxylane.main(["account"]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["data"]["pool_gb"], 1)


if __name__ == "__main__":
    unittest.main()
