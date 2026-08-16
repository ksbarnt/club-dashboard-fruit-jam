# SPDX-License-Identifier: MIT
"""dashboard_client - a CircuitPython client for club-dashboard-web's
external cached-data API.

Replaces ``cpvexevents.VexEventsClient`` as this dashboard's only network
data source: instead of calling events.vex.com directly, every fetch now
reads the pre-shaped, already-cached payload a club-dashboard-web
deployment serves at GET /api/external/{active-teams,world-skills,awards},
authenticated with a static ``X-API-Key`` header. Those payloads are
already exactly the shape this project's old ``vex_data.py`` used to build
by hand from raw VEX Events API responses, so there is no reshaping or
pagination here -- just three small, unparameterized GETs.

This library does not manage WiFi itself -- you construct an
``adafruit_requests.Session`` (or duck-typed equivalent with a
``.get(url, headers=..., timeout=...)`` method) however suits your board,
and hand it to the client, same as ``cpvexevents`` did::

    from dashboard_client import DashboardClient

    client = DashboardClient(session, "https://dashboard.example.org", api_key="...")
    result = client.get_active_teams()
    print(result["IQ"], result["V5"])
"""


class DashboardError(Exception):
    """Base error for all problems talking to club-dashboard-web's API."""

    def __init__(self, message, code=None, status=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status

    def __str__(self):
        if self.status is not None:
            return "[HTTP %s] %s" % (self.status, self.message)
        return str(self.message)


class DashboardConnectionError(DashboardError):
    """Raised when the underlying socket/HTTP request itself fails.

    This covers no-network, DNS failure, TLS errors, timeouts, etc. -
    anything that happens before a response is received from the server.
    """
    pass


class DashboardHTTPError(DashboardError):
    """Raised when the API responds with a 4xx/5xx status code."""
    pass


class DashboardAuthError(DashboardHTTPError):
    """Raised for 401 responses (missing or invalid X-API-Key)."""
    pass


class DashboardNotAvailableError(DashboardHTTPError):
    """Raised for 404 responses whose body is ``{"error": "not_available"}``
    -- that view hasn't been cached by club-dashboard-web yet (nobody has
    loaded its dashboard page to populate it). This is a routine steady
    state for a freshly deployed instance, not necessarily a bug."""
    pass


class DashboardClient(object):
    """Talks to one club-dashboard-web deployment's /api/external/* routes.

    :param session: An ``adafruit_requests.Session`` instance (or any
        object with a duck-typed ``.get(url, headers=..., timeout=...)``
        method returning a response with ``.status_code``, ``.json()``
        and ``.close()``). This library never imports networking modules
        itself.
    :param base_url: club-dashboard-web's origin, e.g.
        "https://dashboard.example.org". A trailing slash is stripped
        automatically if present.
    :param api_key: The raw static API key club-dashboard-web was
        configured with (not the SHA-256 hash stored in its .env). Sent
        as the X-API-Key header on every request.
    :param timeout: Socket timeout in seconds, passed through to the
        session's ``get()`` when it accepts one.
    """

    def __init__(self, session, base_url, api_key, timeout=10):
        if session is None:
            raise ValueError(
                "session is required - pass an adafruit_requests.Session "
                "(or duck-typed equivalent)."
            )
        self._session = session
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # -- low-level plumbing --------------------------------------------

    def _headers(self):
        return {"Accept": "application/json", "X-API-Key": self.api_key}

    def _get(self, path):
        url = self.base_url + path
        headers = self._headers()
        try:
            try:
                resp = self._session.get(url, headers=headers, timeout=self.timeout)
            except TypeError:
                # Some Session implementations don't accept a timeout kwarg.
                resp = self._session.get(url, headers=headers)
        except Exception as exc:
            raise DashboardConnectionError("Request to %s failed: %s" % (url, exc))
        try:
            return self._handle_response(resp, url)
        finally:
            try:
                resp.close()
            except Exception:
                pass

    def _handle_response(self, resp, url):
        status = resp.status_code
        if status >= 400:
            payload = None
            try:
                payload = resp.json()
            except Exception:
                payload = None
            message = None
            code = None
            if isinstance(payload, dict):
                message = payload.get("message")
                code = payload.get("error")
            if not message:
                message = "HTTP %s error for %s" % (status, url)
            if status == 404 and code == "not_available":
                raise DashboardNotAvailableError(message, code=code, status=status)
            if status in (401, 403):
                raise DashboardAuthError(message, code=code, status=status)
            raise DashboardHTTPError(message, code=code, status=status)
        try:
            return resp.json()
        except Exception as exc:
            raise DashboardError(
                "Could not decode JSON response from %s: %s" % (url, exc)
            )

    # -- endpoints --------------------------------------------------------

    def get_active_teams(self):
        """{"IQ": [...], "V5": [...], "warnings": [...], ...}"""
        return self._get("/api/external/active-teams")

    def get_world_skills(self):
        """{"groups": [...], "eventRegion": str, ...}"""
        return self._get("/api/external/world-skills")

    def get_awards(self):
        """{"VIQRC": [...], "V5RC": [...], "warnings": [...], ...}"""
        return self._get("/api/external/awards")
