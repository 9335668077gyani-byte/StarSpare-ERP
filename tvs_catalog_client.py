# tvs_catalog_client.py
# Ported from: github.com/9335668077gyani-byte/cateloge_data_base/Nexses_eCatalog/api_sync_engine.py
# Trimmed for spare_ERP vehicle compatibility lookup use only.
# IMPORTANT: Rate limiting is mandatory. Do NOT call in bulk loops.

import json
import time
import random
import requests

BASE_URL          = "https://www.advantagetvs.com/PartEcommerceAPI"
DEFAULT_DEALER_ID = "63050"
DEFAULT_BRANCH_ID = 1

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.advantagetvs.com/NewPartsECatalog/",
    "Origin":          "https://www.advantagetvs.com",
    "Connection":      "keep-alive",
}


def _stealth_sleep(min_s: float = 1.5, max_s: float = 3.5):
    """Random delay between API calls to avoid rate-limiting."""
    time.sleep(random.uniform(min_s, max_s))


def _clean_json(data):
    """Recursively unwrap double/triple-encoded JSON strings from the TVS API."""
    if isinstance(data, str):
        s = data.strip()
        if s.startswith('"') and s.endswith('"') and len(s) >= 2:
            s_u = s[1:-1].replace('\\"', '"').replace('\\\\"', '\\"')
            if s_u.startswith(("{", "[")):
                s = s_u
        if s.startswith(("{", "[")):
            try:
                return _clean_json(json.loads(s))
            except Exception:
                pass
        return data
    elif isinstance(data, list):
        return [_clean_json(i) for i in data]
    elif isinstance(data, dict):
        return {k: _clean_json(v) for k, v in data.items()}
    return data


class TVSCatalogClient:
    """
    Minimal TVS Advantage eCatalog API client for spare_ERP vehicle compatibility lookup.

    Usage:
        client = TVSCatalogClient(dealer_id="63050")
        if client.connect():
            results = client.search_parts("brake pad")
            # returns list of {"PartNo": ..., "Series": ..., "Description": ...}
    """

    def __init__(self, dealer_id: str = DEFAULT_DEALER_ID, branch_id: int = DEFAULT_BRANCH_ID):
        self.dealer_id = dealer_id
        self.branch_id = branch_id
        self.token     = None
        self.session   = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)

    # ── Internal ──────────────────────────────────────────────────────

    def _get(self, endpoint: str, params: dict = None, timeout: int = 30):
        url = f"{BASE_URL}{endpoint}"
        try:
            if self.token:
                self.session.headers["Authorization"] = f"Bearer {self.token}"
            resp = self.session.get(url, params=params, timeout=timeout)

            # WAF / Rate-limit backoff (up to 3 retries, 30s each)
            retries = 3
            while resp.status_code in (403, 429) and retries > 0:
                time.sleep(30)
                resp = self.session.get(url, params=params, timeout=timeout)
                retries -= 1

            if resp.status_code == 200:
                return _clean_json(resp.json())
            elif resp.status_code == 401:
                # Token expired — re-authenticate silently
                if self._authenticate():
                    self.session.headers["Authorization"] = f"Bearer {self.token}"
                    resp = self.session.get(url, params=params, timeout=timeout)
                    if resp.status_code == 200:
                        return _clean_json(resp.json())
            return None
        except requests.exceptions.RequestException:
            return None
        except (json.JSONDecodeError, ValueError):
            return None

    # ── Authentication ────────────────────────────────────────────────

    def _authenticate(self) -> bool:
        """Obtain a Bearer token from the TVS tokenGeneration endpoint."""
        url     = f"{BASE_URL}/Setting/tokenGeneration"
        # NOTE: tokenGeneration uses dealerId=10001 as a generic anonymous
        # customer accessor — NOT the actual dealer ID (which goes in search queries)
        payload = {"dealerId": 10001, "branchId": 1, "Type": "Customer"}
        try:
            resp = self.session.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    self.token = (
                        data.get("access_token")
                        or data.get("token")
                        or data.get("Token")
                    )
                elif isinstance(data, str):
                    self.token = data
                return bool(self.token)
            return False
        except Exception:
            return False

    def connect(self) -> bool:
        """Authenticate with the TVS API. Returns True if ready."""
        return self._authenticate()

    def is_connected(self) -> bool:
        return bool(self.token)

    # ── Public API ────────────────────────────────────────────────────

    def search_parts(self, keyword: str, page: int = 1, page_size: int = 50) -> list:
        """
        Search TVS eCatalog by part description keyword.

        Returns a list of dicts:
            [{"PartNo": "...", "Series": "...", "Description": "...", "MRP": ...}, ...]

        Rate limiting: a random 1.5–3.5s delay is applied before the call.
        """
        _stealth_sleep()

        data = self._get(
            "/api/Catalouge/GetPartsearch",
            params={
                "dealerId":     self.dealer_id,
                "partid":       "",
                "description":  "",
                "partdesc":     keyword.strip(),
                "partSeries":   "",
                "modelID":      "",
                "page":         page,
                "pageSize":     page_size,
                "frameNumber":  "",
            },
        )

        if not data:
            return []

        # Unwrap envelope
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if isinstance(data, dict) and "PartsLst" in data:
            data = data["PartsLst"]
        if not isinstance(data, list):
            return []

        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            part_no     = str(item.get("PartNo") or item.get("PART_NO") or "").strip()
            series      = str(item.get("Series") or item.get("SERIES") or "").strip()
            series_name = str(
                item.get("SeriesName") or item.get("SERIES_NAME") or
                item.get("ModelName")  or item.get("MODEL_NAME") or
                item.get("CategoryName") or item.get("CATEGORY_NAME") or ""
            ).strip()
            desc    = str(
                item.get("PartDescription")
                or item.get("PART_DESC")
                or item.get("Description")
                or ""
            ).strip()
            mrp = item.get("MRP") or item.get("mrp") or 0
            if not series:
                continue
            results.append({
                "PartNo": part_no, "Series": series,
                "SeriesName": series_name,
                "Description": desc, "MRP": mrp,
                # keep raw item so caller can inspect all fields
                "_raw": item,
            })

        return results
