"""Checks for analyze rate limits and CORS settings."""

import os
import unittest
from unittest.mock import patch

from backend.config import get_cors_origins
from backend.services.rate_limit import RateLimiter, rate_limit_message, reset_limiter


class RateLimitTests(unittest.TestCase):
    def test_limiter_blocks_after_the_cap_then_allows_later(self):
        limiter = RateLimiter(limit=2, window=10)
        self.assertTrue(limiter.allow("a", now=0))
        self.assertTrue(limiter.allow("a", now=1))
        self.assertFalse(limiter.allow("a", now=2))
        self.assertTrue(limiter.allow("b", now=2))
        self.assertTrue(limiter.allow("a", now=12))

    def test_analyze_route_returns_429(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        with patch.dict(os.environ, {"ANALYZE_RATE_LIMIT": "1"}, clear=False):
            reset_limiter()
            try:
                client = TestClient(app)
                first = client.post("/analyze/text", json={"text": "hello internship offer"})
                second = client.post("/analyze/text", json={"text": "hello internship offer"})
            finally:
                reset_limiter()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["detail"], rate_limit_message())

    def test_health_is_not_rate_limited(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        with patch.dict(os.environ, {"ANALYZE_RATE_LIMIT": "1"}, clear=False):
            reset_limiter()
            try:
                client = TestClient(app)
                client.post("/analyze/text", json={"text": "hello internship offer"})
                client.post("/analyze/text", json={"text": "hello internship offer"})
                health = client.get("/health")
            finally:
                reset_limiter()
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok"})


class CorsSettingTests(unittest.TestCase):
    def test_cors_origins_come_from_the_setting(self):
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": "http://localhost:8080, http://127.0.0.1:8080"},
            clear=False,
        ):
            self.assertEqual(
                get_cors_origins(),
                ["http://localhost:8080", "http://127.0.0.1:8080"],
            )

    def test_missing_cors_setting_keeps_the_vite_defaults(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=False):
            origins = get_cors_origins()
        self.assertIn("http://localhost:5173", origins)
        self.assertIn("http://127.0.0.1:5173", origins)
        self.assertIn("http://localhost:5174", origins)
