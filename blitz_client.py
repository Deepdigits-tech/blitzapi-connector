"""BlitzAPI v2 Python Client — wraps all endpoints."""

import time
import requests


class BlitzClient:
    BASE_URL = "https://api.blitz-api.ai/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": api_key,
            "Content-Type": "application/json",
        })
        self._last_request_time = 0

    def _throttle(self):
        """Enforce 200ms between requests (max 5 req/sec)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        self._last_request_time = time.time()

    def _post(self, path: str, payload: dict) -> dict:
        self._throttle()
        url = f"{self.BASE_URL}{path}"
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, params: dict | None = None) -> dict:
        self._throttle()
        url = f"{self.BASE_URL}{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Account ──────────────────────────────────────────────

    def get_key_info(self) -> dict:
        """GET /v2/account/key-info — credits, plan, rate limits."""
        return self._get("/account/key-info")

    # ── Company Search & Enrichment ──────────────────────────

    def find_companies(
        self,
        keywords_include: list[str] | None = None,
        keywords_exclude: list[str] | None = None,
        industry_include: list[str] | None = None,
        industry_exclude: list[str] | None = None,
        country_codes: list[str] | None = None,
        city_include: list[str] | None = None,
        employee_min: int | None = None,
        employee_max: int | None = None,
        max_results: int = 25,
    ) -> dict:
        """POST /v2/search/companies — search by keywords, industry, location, size."""
        company: dict = {}
        if keywords_include or keywords_exclude:
            kw: dict = {}
            if keywords_include:
                kw["include"] = keywords_include
            if keywords_exclude:
                kw["exclude"] = keywords_exclude
            company["keywords"] = kw
        if industry_include or industry_exclude:
            ind: dict = {}
            if industry_include:
                ind["include"] = industry_include
            if industry_exclude:
                ind["exclude"] = industry_exclude
            company["industry"] = ind
        if country_codes or city_include:
            hq: dict = {}
            if country_codes:
                hq["country_code"] = country_codes
            if city_include:
                hq["city"] = {"include": city_include}
            company["hq"] = hq
        if employee_min is not None or employee_max is not None:
            ec: dict = {}
            if employee_min is not None:
                ec["min"] = employee_min
            if employee_max is not None:
                ec["max"] = employee_max
            company["employee_count"] = ec
        payload: dict = {"max_results": max_results}
        if company:
            payload["company"] = company
        return self._post("/search/companies", payload)

    def enrich_company(self, linkedin_url: str) -> dict:
        """POST /v2/enrichment/company — full profile from LinkedIn URL."""
        return self._post("/enrichment/company", {"company_linkedin_url": linkedin_url})

    def domain_to_linkedin(self, domain: str) -> dict:
        """POST /v2/enrichment/domain-to-linkedin — domain → LinkedIn company URL."""
        return self._post("/enrichment/domain-to-linkedin", {"domain": domain})

    def linkedin_to_domain(self, linkedin_url: str) -> dict:
        """POST /v2/enrichment/linkedin-to-domain — LinkedIn URL → email domain."""
        return self._post("/enrichment/linkedin-to-domain", {"company_linkedin_url": linkedin_url})

    # ── People Search ────────────────────────────────────────

    def find_employees(
        self,
        company_linkedin_url: str,
        job_level: list[str] | None = None,
        job_function: list[str] | None = None,
        max_results: int = 25,
        page: int = 1,
    ) -> dict:
        """POST /v2/search/employee-finder — find employees at a company."""
        payload: dict = {
            "company_linkedin_url": company_linkedin_url,
            "max_results": max_results,
            "page": page,
        }
        if job_level:
            payload["job_level"] = job_level
        if job_function:
            payload["job_function"] = job_function
        return self._post("/search/employee-finder", payload)

    def waterfall_icp_search(
        self,
        company_linkedin_url: str,
        cascade: list[dict] | None = None,
        max_results: int = 5,
    ) -> dict:
        """POST /v2/search/waterfall-icp-keyword — find decision-makers by title cascade."""
        payload: dict = {
            "company_linkedin_url": company_linkedin_url,
            "max_results": max_results,
        }
        if cascade:
            payload["cascade"] = cascade
        return self._post("/search/waterfall-icp-keyword", payload)

    # ── People Enrichment ────────────────────────────────────

    def find_work_email(self, linkedin_url: str) -> dict:
        """POST /v2/enrichment/email — SMTP-validated work email."""
        return self._post("/enrichment/email", {"person_linkedin_url": linkedin_url})

    def find_phone(self, linkedin_url: str) -> dict:
        """POST /v2/enrichment/phone — mobile/direct phone (Mega plan)."""
        return self._post("/enrichment/phone", {"person_linkedin_url": linkedin_url})

    def reverse_email_lookup(self, email: str) -> dict:
        """POST /v2/enrichment/email-to-person — person from email."""
        return self._post("/enrichment/email-to-person", {"email": email})

    def reverse_phone_lookup(self, phone: str) -> dict:
        """POST /v2/enrichment/phone-to-person — person from phone."""
        return self._post("/enrichment/phone-to-person", {"phone": phone})
