"""URL and domain features for a job or internship link.

The React page does not open the link. HTTPS, the suspicious-TLD check, and
the subdomain count are computed locally.

These lookups can be unknown instead of raising:

- ``domain_age`` when WHOIS times out, the host has no domain, or WHOIS has
  no creation date
- ``redirects`` when the check times out, the URL is not http(s), or the host
  is not a public address
- ``virustotal`` stays off unless ``VIRUSTOTAL_API_KEY`` is set. A failed or
  timed-out VirusTotal call is unknown

The redirect check sends HEAD requests and does not download the page. It
follows at most five redirects.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import ssl
import threading

import certifi
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote, urljoin, urlparse

import tldextract
import whois

_TLD_PATH = Path(__file__).resolve().parent.parent / "data" / "suspicious_tlds.txt"
_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())
_DOMAIN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5
_MAX_URL_LENGTH = 2048
_USER_AGENT = "InternGuard-URL-Check"
_VT_HOST = "www.virustotal.com"
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class FlagFeature(TypedDict):
    value: bool


class SubdomainFeature(TypedDict):
    value: int
    subdomain: str


class DomainAgeFeature(TypedDict):
    status: str
    days: int | None
    created: str | None
    error: str


class RedirectFeature(TypedDict):
    status: str
    length: int | None
    destination: str | None
    error: str


class VirusTotalFeature(TypedDict):
    status: str
    malicious: int | None
    suspicious: int | None
    error: str


class SuspiciousTldFeature(TypedDict):
    value: bool
    tld: str


class UrlFeatures(TypedDict):
    registered_domain: str
    https: FlagFeature
    suspicious_tld: SuspiciousTldFeature
    subdomain_count: SubdomainFeature
    domain_age: DomainAgeFeature
    redirects: RedirectFeature
    virustotal: VirusTotalFeature


class FeatureLookupError(Exception):
    def __init__(self, error: str) -> None:
        super().__init__(error)
        self.error = error


def extract_url_features(
    url: str | None,
    *,
    timeout: float = 5.0,
    tld_path: Path | None = None,
) -> UrlFeatures:
    """Return URL features for one link.

    ``timeout`` is the per-lookup limit in seconds for WHOIS, redirects, and
    VirusTotal. A timed-out lookup sets that feature's status to ``unknown``.
    """
    raw = _as_text(url).strip()
    parsed = _parse_url(raw)
    extracted = _EXTRACTOR(raw)
    domain = _registered_domain(extracted.top_domain_under_public_suffix)
    return {
        "registered_domain": domain,
        "https": {"value": parsed.scheme.lower() == "https"},
        "suspicious_tld": _suspicious_tld(extracted.suffix, tld_path or _TLD_PATH),
        "subdomain_count": _subdomain_count(extracted.subdomain),
        "domain_age": _domain_age(domain, timeout),
        "redirects": _redirects(raw, timeout),
        "virustotal": _virustotal(domain, timeout),
    }


def _as_text(url: str | None) -> str:
    if url is None:
        return ""
    if isinstance(url, str):
        return url
    return str(url)


def _parse_url(url: str):
    parsed = urlparse(url)
    if not parsed.scheme and not parsed.netloc and url:
        return urlparse("//" + url)
    return parsed


def _registered_domain(domain: str | None) -> str:
    if not domain:
        return ""
    try:
        normalized = domain.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError:
        return ""
    if _DOMAIN.fullmatch(normalized):
        return normalized
    return ""


def _load_tlds(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        tld = line.split("#", 1)[0].strip().lower().lstrip(".")
        if tld:
            found.add(tld)
    return found


def _suspicious_tld(suffix: str, path: Path) -> SuspiciousTldFeature:
    tld = suffix.lower().strip(".")
    listed = _load_tlds(path)
    last_label = tld.split(".")[-1] if tld else ""
    return {"value": bool(tld) and (tld in listed or last_label in listed), "tld": tld}


def _subdomain_count(subdomain: str) -> SubdomainFeature:
    labels = [label for label in subdomain.split(".") if label]
    return {"value": len(labels), "subdomain": subdomain}


def _domain_age(domain: str, timeout: float) -> DomainAgeFeature:
    if not domain:
        return _unknown_age("no domain")
    try:
        created = _run_with_timeout(lambda: _lookup_whois(domain, timeout), timeout)
    except TimeoutError:
        return _unknown_age("timed out")
    except FeatureLookupError as exc:
        return _unknown_age(exc.error)
    except Exception:
        return _unknown_age("lookup failed")
    when = _coerce_date(created)
    if when is None:
        return _unknown_age("creation date missing")
    return {
        "status": "ok",
        "days": (date.today() - when).days,
        "created": when.isoformat(),
        "error": "",
    }


def _lookup_whois(domain: str, timeout: float):
    try:
        record = whois.whois(domain, timeout=timeout)
    except TypeError:
        record = whois.whois(domain)
    if record is None:
        return None
    return getattr(record, "creation_date", None)


def _coerce_date(value) -> date | None:
    if isinstance(value, list):
        found = [item for item in (_coerce_date(entry) for entry in value) if item]
        return min(found) if found else None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _unknown_age(error: str) -> DomainAgeFeature:
    return {"status": "unknown", "days": None, "created": None, "error": error}


def _redirects(url: str, timeout: float) -> RedirectFeature:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return _unknown_redirects("unsupported URL")
    if len(url) > _MAX_URL_LENGTH:
        return _unknown_redirects("unsupported URL")
    try:
        found = _run_with_timeout(lambda: _lookup_redirects(url, timeout), timeout)
    except TimeoutError:
        return _unknown_redirects("timed out")
    except FeatureLookupError as exc:
        return _unknown_redirects(exc.error)
    except Exception:
        return _unknown_redirects("lookup failed")
    return {
        "status": "ok",
        "length": found["length"],
        "destination": found["destination"],
        "error": "",
    }


def _lookup_redirects(url: str, timeout: float) -> dict[str, int | str]:
    current = url
    length = 0
    while True:
        _ensure_public_http_url(current)
        status, location = _request_hop(current, timeout)
        if status not in _REDIRECT_STATUSES or not location:
            return {"length": length, "destination": current}
        length += 1
        current = urljoin(current, location.strip())
        if length >= _MAX_REDIRECTS:
            return {"length": length, "destination": current}


def _request_hop(url: str, timeout: float) -> tuple[int, str | None]:
    import http.client

    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    port = parsed.port
    if parsed.scheme == "https":
        connection = http.client.HTTPSConnection(
            parsed.hostname,
            port or 443,
            timeout=timeout,
            context=_SSL_CONTEXT,
        )
    else:
        connection = http.client.HTTPConnection(parsed.hostname, port or 80, timeout=timeout)
    try:
        connection.request("HEAD", path, headers={"User-Agent": _USER_AGENT})
        response = connection.getresponse()
        status = response.status
        location = response.getheader("Location")
        response.close()
        return status, location
    finally:
        connection.close()


def _ensure_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if parsed.scheme.lower() not in {"http", "https"} or not host:
        raise FeatureLookupError("unsupported URL")
    if host.lower() == "localhost" or host.lower().endswith(".localhost"):
        raise FeatureLookupError("blocked address")
    literal = _literal_ip(host)
    if literal is not None:
        if not literal.is_global:
            raise FeatureLookupError("blocked address")
        return
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise FeatureLookupError("could not resolve host") from exc
    if not infos:
        raise FeatureLookupError("could not resolve host")
    for info in infos:
        resolved = ipaddress.ip_address(info[4][0])
        if not resolved.is_global:
            raise FeatureLookupError("blocked address")


def _literal_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if host.isdigit():
        number = int(host)
        if 0 <= number <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(number)
    return None


def _unknown_redirects(error: str) -> RedirectFeature:
    return {"status": "unknown", "length": None, "destination": None, "error": error}


def _virustotal(domain: str, timeout: float) -> VirusTotalFeature:
    api_key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
    if not api_key or any(character.isspace() for character in api_key):
        return _vt_off()
    if not domain:
        return _unknown_vt("no domain")
    try:
        stats = _run_with_timeout(lambda: _lookup_virustotal(domain, api_key, timeout), timeout)
    except TimeoutError:
        return _unknown_vt("timed out")
    except FeatureLookupError as exc:
        return _unknown_vt(exc.error)
    except Exception:
        return _unknown_vt("lookup failed")
    return {
        "status": "ok",
        "malicious": stats["malicious"],
        "suspicious": stats["suspicious"],
        "error": "",
    }


def _lookup_virustotal(domain: str, api_key: str, timeout: float) -> dict[str, int]:
    import http.client

    connection = http.client.HTTPSConnection(_VT_HOST, timeout=timeout, context=_SSL_CONTEXT)
    try:
        connection.request(
            "GET",
            "/api/v3/domains/" + quote(domain, safe=""),
            headers={"x-apikey": api_key, "User-Agent": _USER_AGENT},
        )
        response = connection.getresponse()
        body = response.read(100_000)
        status = response.status
    finally:
        connection.close()
    if status != 200:
        raise FeatureLookupError("lookup failed")
    payload = json.loads(body.decode("utf-8", errors="replace"))
    stats = payload.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
    return {
        "malicious": int(stats.get("malicious", 0)),
        "suspicious": int(stats.get("suspicious", 0)),
    }


def _vt_off() -> VirusTotalFeature:
    return {
        "status": "off",
        "malicious": None,
        "suspicious": None,
        "error": "VIRUSTOTAL_API_KEY is not set.",
    }


def _unknown_vt(error: str) -> VirusTotalFeature:
    return {"status": "unknown", "malicious": None, "suspicious": None, "error": error}


def _run_with_timeout(fn, timeout: float):
    box: dict = {}

    def runner() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError("timed out")
    if "error" in box:
        raise box["error"]
    return box.get("value")
