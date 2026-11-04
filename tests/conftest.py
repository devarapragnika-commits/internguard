"""Keep the suite offline: no WHOIS or VirusTotal calls."""

from datetime import datetime
from unittest.mock import patch

import pytest

from backend.services import url_features


@pytest.fixture(autouse=True)
def _stub_url_lookups():
    with patch.object(url_features, "_lookup_whois", return_value=datetime(2018, 1, 15)):
        with patch.object(
            url_features,
            "_lookup_virustotal",
            side_effect=AssertionError("VirusTotal was called"),
        ):
            yield
