#!/usr/bin/env python3
"""
🚀 Remote Job Alert — Telegram Edition

Python 3.10+ / standard library only.

TARGETS
-------
1. Frontend: React/Vue/Next/Nuxt/UI/Web roles. No seniority requirement.
2. Software Engineering: mid-level and above.
3. Solution / Software Architecture: mid-level and above.
4. Customer Care / Support: no seniority requirement; ONLY English or Yoruba.

WORK MODEL
----------
Frontend / software / architecture:
  Remote or relocation / visa sponsorship.

Customer care:
  Remote worldwide, OR hybrid/on-site in Porto / Vila Nova de Gaia.
  Language must be English or Yoruba. Portuguese/German/French/Spanish/etc.
  requirements are rejected.

MID-LEVEL
---------
Accepted examples:
  Mid-Level Software Engineer
  Mid Level Software Engineer
  Intermediate Software Engineer
  Software Engineer II
  Software Engineer III
  Developer II / Developer III
  Senior / Staff / Lead / Principal

Plain "Software Engineer" is NOT automatically treated as mid-level.

EUROPEAN SOURCES
----------------
Live/public feeds when available:
  - EURES (configurable API)
  - France Travail (credentialed API)
  - JobsIreland public browse page
  - Arbeitnow (European/Germany-oriented public API)

Official live search links are also sent to Telegram for:
  - EURES
  - Net-Empregos
  - EuroJobs
  - IEFP
  - Bundesagentur für Arbeit
  - France Travail
  - Empléate
  - UWV
  - JobsIreland

The bot does NOT fabricate vacancies when a portal does not expose a
stable unrestricted public API. Those portals appear as official search links.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


# ============================================================================
# CONFIG
# ============================================================================

SEEN_FILE = Path(os.getenv("SEEN_FILE", "seen_jobs.json"))
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "15"))
MAX_PER_SOURCE = int(os.getenv("MAX_PER_SOURCE", "100"))
MAX_ATS_BOARDS = int(os.getenv("MAX_ATS_BOARDS", "60"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
ATS_TIMEOUT = int(os.getenv("ATS_TIMEOUT", "8"))

USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; RemoteJobAlert/5.0; +https://github.com/)",
)

TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")

# Optional APIs.
FINDWORK_KEY = os.getenv("FINDWORK_KEY", "")
EURES_API_URL = os.getenv("EURES_API_URL", "")
FRANCE_TRAVAIL_CLIENT_ID = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "")
FRANCE_TRAVAIL_CLIENT_SECRET = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "")


# ============================================================================
# ROLE FILTERS
# ============================================================================

FRONTEND_TITLE_KW = [
    "frontend engineer",
    "frontend developer",
    "frontend software engineer",
    "frontend software developer",
    "front-end engineer",
    "front-end developer",
    "front end engineer",
    "front end developer",
    "react engineer",
    "react developer",
    "vue engineer",
    "vue developer",
    "next.js engineer",
    "nextjs engineer",
    "next.js developer",
    "nextjs developer",
    "nuxt engineer",
    "nuxt developer",
    "ui engineer",
    "ui developer",
    "web engineer",
    "web developer",
    "software engineer frontend",
    "software developer frontend",
]

ARCHITECTURE_TITLE_KW = [
    "software architect",
    "solution architect",
    "solutions architect",
    "application architect",
    "technical architect",
    "developer architect",
    "cloud architect",
    "software architecture",
]

SOFTWARE_TITLE_KW = [
    "software engineer",
    "software developer",
    "software development engineer",
    "full stack engineer",
    "full-stack engineer",
    "full stack developer",
    "full-stack developer",
]

# IMPORTANT: customer classification is TITLE-ONLY.
# A technical listing mentioning "customers" in the description is not enough.
CUSTOMER_TITLE_KW = [
    "customer care",
    "customer care representative",
    "customer service",
    "customer service representative",
    "customer support",
    "customer support representative",
    "customer experience",
    "customer experience specialist",
    "client support",
    "client services",
    "technical support",
    "technical support specialist",
    "technical support engineer",
    "support specialist",
    "support representative",
    "support agent",
    "customer success",
    "customer success specialist",
    "customer success manager",
    "contact centre",
    "contact center",
    "call center",
    "call centre",
    "help desk",
    "helpdesk",
    "service desk",
    "chat support",
    "email support",
    "customer advisor",
    "customer service advisor",
]

FRONTEND_STACK_KW = [
    "react", "next.js", "nextjs", "vue", "nuxt", "svelte",
    "typescript", "javascript", "solidjs", "astro", "remix",
]

FRONTEND_CONTEXT_KW = [
    "frontend", "front-end", "front end", "web application", "web app",
]

# Explicitly includes mid-level and Roman-numeral engineering levels.
SENIORITY_TITLE_PATTERNS = [
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\bstaff\b",
    r"\blead\b",
    r"\bprincipal\b",
    r"\bmid[- ]?level\b",
    r"\bintermediate\b",
    r"\b(?:engineer|developer)\s+ii\b",
    r"\b(?:engineer|developer)\s+iii\b",
    r"\b(?:engineer|developer)\s+iv\b",
    r"\b(?:engineer|developer)\s+2\b",
    r"\b(?:engineer|developer)\s+3\b",
    r"\b(?:engineer|developer)\s+4\b",
]

HARD_EXCLUDE_PATTERNS = [
    r"\bintern(?:ship)?\b",
    r"\bjunior\b",
    r"\bjr\.?\b",
    r"\bentry[- ]level\b",
    r"\bgraduate\b",
    r"\bapprentice\b",
    r"\btrainee\b",
    r"\bbackend engineer\b",
    r"\bback[- ]end engineer\b",
    r"\bbackend developer\b",
    r"\bback[- ]end developer\b",
    r"\bios engineer\b",
    r"\bios developer\b",
    r"\bandroid engineer\b",
    r"\bandroid developer\b",
    r"\bdevops\b",
    r"\bplatform engineer\b",
    r"\bsre\b",
    r"\bsite reliability\b",
    r"\bqa engineer\b",
    r"\btest engineer\b",
    r"\bdata engineer\b",
    r"\bmachine learning engineer\b",
    r"\bai engineer\b",
    r"\bml engineer\b",
    r"\bproduct manager\b",
    r"\bproduct designer\b",
    r"\bux designer\b",
    r"\baccount manager\b",
    r"\brecruiter\b",
    r"\btalent acquisition\b",
    r"\boperations engineer\b",
    r"\bfield service\b",
    r"\bservice technician\b",
    r"\btechnician\b",
    r"\bdispense technician\b",
    r"\bdelivery manager\b",
    r"\bproject manager\b",
    r"\bprogram manager\b",
    r"\bdata entry\b",
    r"\badministrator\b",
    r"\bassistant\b",
]

COMMERCIAL_EXCLUDE_PATTERNS = [
    r"\bsales representative\b",
    r"\bsales executive\b",
    r"\bsales manager\b",
    r"\bbusiness development\b",
    r"\bmarketing specialist\b",
    r"\bmarketing manager\b",
]

LIVE_CODING_PATTERNS = [
    r"\blive coding\b",
    r"\blive[- ]coding\b",
    r"\bcoding interview\b",
    r"\bpair programming interview\b",
    r"\bcodility\b",
    r"\bhackerrank\b",
    r"\bleetcode\b",
]

REMOTE_KW = [
    "remote", "fully remote", "100% remote", "remote work", "work remotely",
    "work from home", "wfh", "remote-first", "remote only", "distributed",
    "distributed team", "anywhere", "work from anywhere", "location independent",
    "fully distributed", "home based", "home-based",
]

RELOCATION_KW = [
    "visa sponsorship", "work visa", "visa support", "relocation", "relocate",
    "moving allowance", "relocation package", "sponsorship available",
]

REMOTE_NEGATIVE_PATTERNS = [
    r"\bnot remote\b",
    r"\bno remote\b",
    r"\bremote not available\b",
    r"\bremote unavailable\b",
]

HYBRID_KW = ["hybrid", "hybrid work", "hybrid role", "hybrid position"]
ONSITE_KW = ["on-site", "onsite", "on site", "office-based", "office based"]
PORTO_KW = [
    "porto", "oporto", "porto, portugal", "porto portugal",
    "vila nova de gaia", "gaia, portugal",
]

ALLOWED_CUSTOMER_LANGUAGES = [
    "english", "english speaking", "english-speaking", "fluent english",
    "native english", "english fluency", "yoruba",
]

CUSTOMER_UNWANTED_LANGUAGE_PATTERNS = [
    r"\bportuguese(?: speaking| language| required| fluency)?\b",
    r"\bgerman(?: speaking| language| required| fluency)?\b",
    r"\bfrench(?: speaking| language| required| fluency)?\b",
    r"\bspanish(?: speaking| language| required| fluency)?\b",
    r"\bdutch(?: speaking| language| required| fluency)?\b",
    r"\bitalian(?: speaking| language| required| fluency)?\b",
]

SEARCH_TERMS = [
    "frontend engineer",
    "frontend developer",
    "react developer",
    "react engineer",
    "vue developer",
    "software engineer",
    "software engineer II",
    "software engineer III",
    "solution architect",
    "software architect",
    "customer support",
    "customer service",
    "customer care",
    "technical support",
    "support specialist",
    "help desk",
]


# ============================================================================
# EUROPEAN PORTAL LINKS
# ============================================================================

EUROPEAN_PORTALS = {
    "EURES": "https://europa.eu/eures/portal/jv-se/search?keywordsEverywhere={query}&lang=en",
    "Net-Empregos": "https://www.net-empregos.com/pesquisa-empregos.asp?chaves={query}",
    "EuroJobs": "https://www.eurojobs.com/search/?keywords={query}",
    "IEFP": "https://iefponline.iefp.pt/IEFP/search.do?cat=ofertaEmprego",
    "Bundesagentur für Arbeit": "https://www.arbeitsagentur.de/jobsuche/?was={query}",
    "France Travail": "https://candidat.francetravail.fr/offres/recherche?motsCles={query}",
    "Empléate": "https://empleate.gob.es/empleo/",
    "UWV": "https://www.werk.nl/werkzoekenden/vacatures/",
    "JobsIreland": "https://jobsireland.ie/en-US/browse-jobs?keyWord={query}",
}


# ============================================================================
# HELPERS
# ============================================================================

def clean_text(value: Any) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: Any) -> str:
    return clean_text(value).lower()


def truncate(value: Any, size: int) -> str:
    return clean_text(value)[:size]


def matches_any(text: str, phrases: Iterable[str]) -> bool:
    text = normalize_text(text)
    return any(str(p).lower() in text for p in phrases)


def matches_patterns(text: str, patterns: Iterable[str]) -> bool:
    text = normalize_text(text)
    return any(re.search(p, text, re.I) for p in patterns)


def fetch_url(url: str, *, headers: dict[str, str] | None = None, timeout: int = REQUEST_TIMEOUT) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def fetch_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = REQUEST_TIMEOUT) -> Any:
    return json.loads(fetch_url(url, headers=headers, timeout=timeout).decode("utf-8-sig"))


def post_form(url: str, data: dict[str, str], *, headers: dict[str, str] | None = None, timeout: int = REQUEST_TIMEOUT) -> Any:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode(),
        headers=request_headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def parse_date(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000 if number > 10_000_000_000 else number
    text = str(value).strip()
    if text.isdigit():
        number = float(text)
        return number / 1000 if number > 10_000_000_000 else number
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        pass
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    return 0.0


def parse_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[,|;/]", value) if x.strip()][:8]
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()][:8]
    return []


def job_id(job: dict) -> str:
    url = str(job.get("url") or "").strip()
    key = url or "|".join([
        normalize_text(job.get("title")),
        normalize_text(job.get("company")),
        normalize_text(job.get("location")),
    ])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        value = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return set(value if isinstance(value, list) else [])
    except (OSError, json.JSONDecodeError):
        print("  [WARN] Could not read seen_jobs.json; starting fresh.")
        return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")


def safe_source_call(name: str, fn: Callable[[], list[dict]]) -> list[dict]:
    try:
        return fn()
    except Exception as exc:
        print(f"  [ERROR] {name}: {exc}")
        return []


# ============================================================================
# CLASSIFICATION
# ============================================================================

def title_contains_any(title: str, keywords: Iterable[str]) -> bool:
    title = normalize_text(title)
    return any(k.lower() in title for k in keywords)


def is_hard_excluded_title(title: str) -> bool:
    return matches_patterns(title, HARD_EXCLUDE_PATTERNS + COMMERCIAL_EXCLUDE_PATTERNS)


def get_role_type(job: dict) -> str | None:
    """Classify from title only to prevent description-based false positives."""
    title = job.get("title", "")
    if is_hard_excluded_title(title):
        return None
    if title_contains_any(title, CUSTOMER_TITLE_KW):
        return "customer"
    if title_contains_any(title, FRONTEND_TITLE_KW):
        return "frontend"
    if title_contains_any(title, ARCHITECTURE_TITLE_KW):
        return "architecture"
    if title_contains_any(title, SOFTWARE_TITLE_KW):
        return "software"
    return None


def is_frontend_role(job: dict) -> bool:
    return get_role_type(job) == "frontend"


def is_customer_care_role(job: dict) -> bool:
    return get_role_type(job) == "customer"


def is_architecture_role(job: dict) -> bool:
    return get_role_type(job) == "architecture"


def is_software_role(job: dict) -> bool:
    return get_role_type(job) == "software"


def get_job_family(job: dict) -> str:
    return {
        "frontend": "Frontend",
        "architecture": "Solution / Software Architecture",
        "software": "Software Engineering",
        "customer": "Customer Care",
    }.get(get_role_type(job) or "", "Other")


def is_mid_senior(job: dict) -> bool:
    """True only when the vacancy title itself shows mid-level-or-above."""
    title = normalize_text(job.get("title", ""))
    if is_hard_excluded_title(title):
        return False
    return any(re.search(pattern, title, re.I) for pattern in SENIORITY_TITLE_PATTERNS)


def is_remote_or_relocation(job: dict) -> bool:
    text = normalize_text(" ".join([
        job.get("location", ""),
        job.get("description", ""),
        " ".join(job.get("tags") or []),
    ]))
    if matches_patterns(text, REMOTE_NEGATIVE_PATTERNS) and not matches_any(text, REMOTE_KW):
        return matches_any(text, RELOCATION_KW)
    return matches_any(text, REMOTE_KW) or matches_any(text, RELOCATION_KW)


def customer_has_allowed_language(job: dict) -> bool:
    text = normalize_text(" ".join([
        job.get("title", ""), job.get("location", ""), job.get("description", ""),
    ]))
    if matches_patterns(text, CUSTOMER_UNWANTED_LANGUAGE_PATTERNS):
        return False
    return matches_any(text, ALLOWED_CUSTOMER_LANGUAGES)


def customer_has_allowed_location(job: dict) -> bool:
    text = normalize_text(" ".join([
        job.get("title", ""), job.get("location", ""), job.get("description", ""),
    ]))
    remote = matches_any(text, REMOTE_KW)
    hybrid = matches_any(text, HYBRID_KW)
    onsite = matches_any(text, ONSITE_KW)
    porto = matches_any(text, PORTO_KW)

    if remote and not hybrid:
        return True
    if (hybrid or onsite) and porto:
        return True
    if not remote and not hybrid and not onsite:
        return porto
    return False


def has_live_coding(job: dict) -> bool:
    return matches_patterns(
        " ".join([job.get("title", ""), job.get("description", "")]),
        LIVE_CODING_PATTERNS,
    )


def explain_rejection(job: dict) -> str:
    role = get_role_type(job)
    if role is None:
        return "not_target_role"

    if role == "customer":
        if not customer_has_allowed_language(job):
            return "customer_language"
        if not customer_has_allowed_location(job):
            return "customer_location"
        return "live_coding" if has_live_coding(job) else "PASS"

    if role == "frontend":
        # Frontend has NO seniority requirement.
        if not is_remote_or_relocation(job):
            return "not_remote_or_relocation"
        return "live_coding" if has_live_coding(job) else "PASS"

    if role in {"software", "architecture"}:
        if not is_mid_senior(job):
            return "not_mid_senior"
        if not is_remote_or_relocation(job):
            return "not_remote_or_relocation"
        return "live_coding" if has_live_coding(job) else "PASS"

    return "not_target_role"


def is_good_job(job: dict) -> bool:
    return explain_rejection(job) == "PASS"


def get_work_type(job: dict) -> str:
    text = normalize_text(" ".join([job.get("location", ""), job.get("description", "")]))
    remote = matches_any(text, REMOTE_KW)
    relocation = matches_any(text, RELOCATION_KW)
    hybrid = matches_any(text, HYBRID_KW)
    onsite = matches_any(text, ONSITE_KW)
    if remote and relocation:
        return "🌍 Remote + Relocation"
    if remote and hybrid:
        return "🌍 Remote / Hybrid"
    if remote:
        return "🏠 Remote"
    if hybrid:
        return "🏢 Hybrid"
    if onsite:
        return "🏢 On-site"
    if relocation:
        return "✈️ Relocation"
    return "📍 Location specified"


# ============================================================================
# JOB FACTORY
# ============================================================================

def make_job(
    title: str,
    company: str,
    url: str,
    source: str,
    *,
    location: str = "Remote",
    tags: Any = None,
    desc: str = "",
    posted_at: Any = 0.0,
) -> dict:
    description = clean_text(desc)
    return {
        "title": truncate(title, 160),
        "company": truncate(company, 100),
        "url": str(url or "").strip(),
        "source": source,
        "location": truncate(location or "Remote", 180),
        "tags": parse_tags(tags),
        "description": description,
        "desc_snippet": truncate(description, 700),
        "posted_at": parse_date(posted_at),
        "job_family": "",
    }


# ============================================================================
# RSS
# ============================================================================

def fetch_rss(url: str, source: str) -> list[dict]:
    jobs = []
    try:
        root = ET.fromstring(fetch_url(url))
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for item in items[:MAX_PER_SOURCE]:
            title = item.findtext("title") or item.findtext("atom:title", namespaces=ns) or ""
            link = item.findtext("link") or ""
            if not link:
                atom_link = item.find("atom:link", ns)
                if atom_link is not None:
                    link = atom_link.attrib.get("href", "")
            desc = item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or ""
            pub = item.findtext("pubDate") or item.findtext("published") or item.findtext("updated") or ""
            job = make_job(title, "", link, source, desc=desc, posted_at=pub)
            if is_good_job(job):
                job["job_family"] = get_job_family(job)
                jobs.append(job)
        return jobs
    except Exception as exc:
        print(f"  [WARN] {source} RSS: {exc}")
        return []


def source_rss() -> list[dict]:
    feeds = [
        ("https://weworkremotely.com/categories/remote-programming-jobs.rss", "WeWorkRemotely"),
        ("https://weworkremotely.com/categories/remote-customer-support-jobs.rss", "WeWorkRemotely/Customer Support"),
    ]
    jobs = []
    for url, name in feeds:
        found = fetch_rss(url, name)
        print(f"  {name}: {len(found)}")
        jobs.extend(found)
    return jobs


# ============================================================================
# GLOBAL SOURCES
# ============================================================================

def source_remoteok() -> list[dict]:
    try:
        data = fetch_json("https://remoteok.com/api")
        records = data[1:] if isinstance(data, list) else []
        jobs = []
        raw = target = 0
        reasons: Counter[str] = Counter()
        target_preview = []

        for item in records[:MAX_PER_SOURCE]:
            raw += 1
            job = make_job(
                item.get("position", ""), item.get("company", ""), item.get("url", ""), "RemoteOK",
                location=item.get("location") or "Remote", tags=item.get("tags", []),
                desc=item.get("description", ""), posted_at=item.get("date", ""),
            )
            reason = explain_rejection(job)
            if get_role_type(job) is not None:
                target += 1
                target_preview.append((job, reason))
            if reason == "PASS":
                job["job_family"] = get_job_family(job)
                jobs.append(job)
            else:
                reasons[reason] += 1

        print(f"  RemoteOK: raw={raw}, target={target}, passed={len(jobs)}")
        if reasons:
            print("    Rejections:")
            for reason, count in reasons.most_common():
                if reason != "not_target_role":
                    print(f"      {reason}: {count}")
        if target_preview:
            print("    Target jobs:")
            for job, reason in target_preview:
                print(f"      - {job['title']} @ {job['company'] or '—'} → {reason}")
        return jobs
    except Exception as exc:
        print(f"  [WARN] RemoteOK: {exc}")
        return []


def source_remotive() -> list[dict]:
    jobs = []
    categories = [("software-dev", "Remotive/Software"), ("customer-service", "Remotive/Customer Support")]
    for category, source_name in categories:
        try:
            url = "https://remotive.com/api/remote-jobs?" + urllib.parse.urlencode({"category": category, "limit": MAX_PER_SOURCE})
            data = fetch_json(url)
            for item in data.get("jobs", []):
                job = make_job(
                    item.get("title", ""), item.get("company_name", ""), item.get("url", ""), source_name,
                    location=item.get("candidate_required_location") or "Remote", tags=item.get("tags", []),
                    desc=item.get("description", ""), posted_at=item.get("publication_date", ""),
                )
                if is_good_job(job):
                    job["job_family"] = get_job_family(job)
                    jobs.append(job)
        except Exception as exc:
            print(f"  [WARN] {source_name}: {exc}")
    print(f"  Remotive: {len(jobs)}")
    return jobs


def source_jobicy() -> list[dict]:
    try:
        url = "https://jobicy.com/api/v2/remote-jobs?" + urllib.parse.urlencode({"count": MAX_PER_SOURCE})
        data = fetch_json(url)
        jobs = []
        for item in data.get("jobs", [])[:MAX_PER_SOURCE]:
            job = make_job(
                item.get("jobTitle", ""), item.get("companyName", ""), item.get("url", ""), "Jobicy",
                location=item.get("jobGeo") or "Remote", desc=item.get("jobDescription", ""),
                posted_at=item.get("pubDate", ""),
            )
            if is_good_job(job):
                job["job_family"] = get_job_family(job)
                jobs.append(job)
        print(f"  Jobicy: {len(jobs)}")
        return jobs
    except Exception as exc:
        print(f"  [WARN] Jobicy: {exc}")
        return []


def source_arbeitnow() -> list[dict]:
    try:
        data = fetch_json("https://www.arbeitnow.com/api/job-board-api")
        jobs = []
        for item in data.get("data", [])[:MAX_PER_SOURCE]:
            job = make_job(
                item.get("title", ""), item.get("company_name", ""), item.get("url", ""), "Arbeitnow",
                location=item.get("location") or "Remote", tags=item.get("tags", []),
                desc=item.get("description", ""), posted_at=item.get("created_at", ""),
            )
            if item.get("remote"):
                job["location"] += " · Remote"
            if is_good_job(job):
                job["job_family"] = get_job_family(job)
                jobs.append(job)
        print(f"  Arbeitnow: {len(jobs)}")
        return jobs
    except Exception as exc:
        print(f"  [WARN] Arbeitnow: {exc}")
        return []


def source_findwork() -> list[dict]:
    if not FINDWORK_KEY:
        print("  FindWork: disabled (set FINDWORK_KEY)")
        return []
    jobs = []
    try:
        url = "https://findwork.dev/api/jobs/?" + urllib.parse.urlencode({"remote": "true"})
        data = fetch_json(url, headers={"Authorization": f"Token {FINDWORK_KEY}"})
        for item in data.get("results", []):
            job = make_job(
                item.get("role", ""), item.get("company_name", ""), item.get("url", ""), "FindWork",
                location="Remote", tags=item.get("keywords", []), desc=" ".join(map(str, item.get("keywords", []))),
                posted_at=item.get("date_posted", ""),
            )
            if is_good_job(job):
                job["job_family"] = get_job_family(job)
                jobs.append(job)
        print(f"  FindWork: {len(jobs)}")
        return jobs
    except Exception as exc:
        print(f"  [WARN] FindWork: {exc}")
        return []


# ============================================================================
# HACKER NEWS
# ============================================================================

def source_hn_hiring() -> list[dict]:
    try:
        search_url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode({
            "query": "Ask HN Who is Hiring", "tags": "ask_hn", "hitsPerPage": 10,
        })
        search = fetch_json(search_url)
        hits = [h for h in search.get("hits", []) if "who is hiring" in normalize_text(h.get("title", ""))]
        if not hits:
            print("  HN Who's Hiring: 0")
            return []
        story_id = hits[0].get("objectID")
        story = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        jobs = []
        for kid in (story.get("kids") or [])[:250]:
            try:
                comment = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{kid}.json", timeout=6)
                text = clean_text(comment.get("text", ""))
                if not text or comment.get("dead") or comment.get("deleted"):
                    continue
                job = make_job(
                    text.split("\n")[0][:160], "HN Who's Hiring",
                    f"https://news.ycombinator.com/item?id={kid}", "HN Who's Hiring",
                    location="Remote / Various", tags=["startup", "direct"], desc=text,
                    posted_at=comment.get("time", 0),
                )
                if is_good_job(job):
                    job["job_family"] = get_job_family(job)
                    jobs.append(job)
            except Exception:
                continue
        print(f"  HN Who's Hiring: {len(jobs)}")
        return jobs
    except Exception as exc:
        print(f"  [WARN] HN Who's Hiring: {exc}")
        return []


# ============================================================================
# ATS SOURCES
# ============================================================================

def _greenhouse_slugs() -> list[str]:
    try:
        data = fetch_json("https://boards-api.greenhouse.io/v1/boards", timeout=10)
        return [b.get("token") for b in data.get("boards", []) if b.get("token")][:MAX_ATS_BOARDS]
    except Exception as exc:
        print(f"  [WARN] Greenhouse discovery: {exc}")
        return ["linear", "vercel", "notion", "loom", "retool", "brex", "rippling", "supabase", "replit", "clerk", "neon", "airbyte", "metabase"]


def source_greenhouse() -> list[dict]:
    jobs = []
    slugs = _greenhouse_slugs()
    for slug in slugs:
        try:
            data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=ATS_TIMEOUT)
            for item in data.get("jobs", []):
                offices = item.get("offices") or []
                location = " ".join(str(o.get("name", "")) for o in offices if o.get("name")) or "Remote"
                job = make_job(item.get("title", ""), slug.replace("-", " ").title(), item.get("absolute_url", ""), "Greenhouse", location=location, tags=["ATS"], desc=item.get("content", ""), posted_at=item.get("updated_at", ""))
                if is_good_job(job):
                    job["job_family"] = get_job_family(job)
                    jobs.append(job)
        except Exception:
            continue
    print(f"  Greenhouse: {len(jobs)} (from {len(slugs)} boards)")
    return jobs


def source_lever() -> list[dict]:
    # Keep a small maintained public list instead of pretending Lever has a global slug API.
    slugs = ["deel", "remote", "canonical", "recharge"]
    jobs = []
    for slug in slugs:
        try:
            data = fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json", timeout=ATS_TIMEOUT)
            for item in data:
                categories = item.get("categories") or {}
                job = make_job(item.get("text", ""), slug.title(), item.get("hostedUrl", ""), "Lever", location=categories.get("location") or "Remote", tags=["ATS"], desc=item.get("descriptionPlain", ""), posted_at=item.get("createdAt", 0))
                if is_good_job(job):
                    job["job_family"] = get_job_family(job)
                    jobs.append(job)
        except Exception:
            continue
    print(f"  Lever: {len(jobs)}")
    return jobs


# ============================================================================
# EURES
# ============================================================================

def source_eures() -> list[dict]:
    if not EURES_API_URL:
        print("  EURES: official search links enabled; live API not configured")
        return []
    jobs = []
    for query in SEARCH_TERMS:
        try:
            url = EURES_API_URL + ("&" if "?" in EURES_API_URL else "?") + urllib.parse.urlencode({
                "page": 1, "resultsPerPage": 50, "orderBy": "MOST_RECENT",
                "keywordsEverywhere": query, "availableLanguages": "en",
            })
            data = fetch_json(url)
            records = data.get("jvs") or data.get("jobs") or data.get("results") or data.get("data") or []
            for item in records:
                job = make_job(
                    item.get("title") or item.get("job_title") or item.get("jobTitle") or "",
                    item.get("company") or item.get("employer_name") or "",
                    item.get("url") or item.get("source_url") or item.get("job_url") or "",
                    "EURES", location=item.get("location") or item.get("location_country") or "Europe",
                    tags=["Europe", "EURES"], desc=item.get("description_text") or item.get("description") or "",
                    posted_at=item.get("publication_date") or item.get("creation_date") or 0,
                )
                if is_good_job(job):
                    job["job_family"] = get_job_family(job)
                    jobs.append(job)
        except Exception as exc:
            print(f"  [WARN] EURES '{query}': {exc}")
    jobs = deduplicate_jobs(jobs)
    print(f"  EURES live API: {len(jobs)}")
    return jobs


# ============================================================================
# FRANCE TRAVAIL
# ============================================================================

def france_travail_token() -> str:
    if not FRANCE_TRAVAIL_CLIENT_ID or not FRANCE_TRAVAIL_CLIENT_SECRET:
        return ""
    data = post_form(
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire",
        {
            "grant_type": "client_credentials",
            "client_id": FRANCE_TRAVAIL_CLIENT_ID,
            "client_secret": FRANCE_TRAVAIL_CLIENT_SECRET,
            "scope": "api_offresdemploiv2 o2dsoffre",
        },
    )
    return data.get("access_token", "")


def source_france_travail() -> list[dict]:
    if not FRANCE_TRAVAIL_CLIENT_ID or not FRANCE_TRAVAIL_CLIENT_SECRET:
        print("  France Travail: official search links enabled; API credentials not configured")
        return []
    try:
        token = france_travail_token()
        if not token:
            return []
        jobs = []
        for query in SEARCH_TERMS:
            url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search?" + urllib.parse.urlencode({
                "motsCles": query,
                "range": f"0-{min(MAX_PER_SOURCE, 149)}",
            })
            data = fetch_json(url, headers={"Authorization": f"Bearer {token}"})
            for item in data.get("resultats", []):
                loc = item.get("lieuTravail") or {}
                location = " ".join(str(loc.get(k, "")) for k in ("libelle", "commune") if loc.get(k))
                job = make_job(item.get("intitule", ""), item.get("entreprise", {}).get("nom", ""), item.get("origineOffre", {}).get("urlOrigine", ""), "France Travail", location=location or "France", tags=["France"], desc=item.get("description", ""), posted_at=item.get("dateCreation", ""))
                if is_good_job(job):
                    job["job_family"] = get_job_family(job)
                    jobs.append(job)
        jobs = deduplicate_jobs(jobs)
        print(f"  France Travail live API: {len(jobs)}")
        return jobs
    except Exception as exc:
        print(f"  [WARN] France Travail API: {exc}")
        return []


# ============================================================================
# JOBSIRELAND PUBLIC PAGE
# ============================================================================

def source_jobsireland() -> list[dict]:
    """Best-effort parser for the public JobsIreland browse page."""
    try:
        url = "https://jobsireland.ie/en-US/browse-jobs?" + urllib.parse.urlencode({
            "keyWord": "customer support",
            "page": 1,
            "pageSize": 100,
        })
        raw = fetch_url(url).decode("utf-8", "ignore")
        # The public page can contain compact semicolon-delimited vacancy data.
        pattern = re.compile(
            r"(?P<lat>-?\d+(?:\.\d+)?);(?P<lon>-?\d+(?:\.\d+)?);(?P<company>[^;<>]{2,140});(?P<title>[^;<>]{2,180});(?P<id>\d{5,})",
            re.I,
        )
        jobs = []
        for match in pattern.finditer(raw):
            title = clean_text(match.group("title"))
            company = clean_text(match.group("company"))
            job = make_job(
                title,
                company,
                f"https://jobsireland.ie/en-US/browse-jobs?vacancyId={match.group('id')}",
                "JobsIreland",
                location="Ireland",
                desc=title,
            )
            if is_good_job(job):
                job["job_family"] = get_job_family(job)
                jobs.append(job)
        jobs = deduplicate_jobs(jobs)
        print(f"  JobsIreland live: {len(jobs)}")
        return jobs[:MAX_PER_SOURCE]
    except Exception as exc:
        print(f"  [WARN] JobsIreland live: {exc}")
        return []


# ============================================================================
# EUROPEAN OFFICIAL SEARCH LINKS
# ============================================================================

def source_european_portals() -> list[dict]:
    """Official live search links for European/national employment portals."""
    records = []
    searches = [
        ("Frontend", "frontend developer"),
        ("Software", "software engineer II"),
        ("Architecture", "solution architect"),
        ("Customer Care", "customer support"),
    ]

    for source, template in EUROPEAN_PORTALS.items():
        for family, query in searches:
            url = template.format(query=urllib.parse.quote_plus(query))
            records.append({
                "title": f"{source} — {query}",
                "company": source,
                "url": url,
                "source": source,
                "location": "Europe",
                "tags": ["official portal", "discovery"],
                "description": f"Official live {source} search for {query}.",
                "desc_snippet": f"Official live {source} search for {query}.",
                "posted_at": 0.0,
                "job_family": family,
                "discovery_only": True,
            })

    print(f"  European job boards: {len(records)} official search links")
    return records


# ============================================================================
# PIPELINE
# ============================================================================

@dataclass(frozen=True)
class Source:
    name: str
    fn: Callable[[], list[dict]]
    enabled: bool = True


SOURCES = [
    Source("RemoteOK", source_remoteok),
    Source("Remotive", source_remotive),
    Source("Jobicy", source_jobicy),
    Source("Arbeitnow", source_arbeitnow),
    Source("FindWork", source_findwork, enabled=bool(FINDWORK_KEY)),
    Source("WeWorkRemotely", source_rss),
    Source("HN Hiring", source_hn_hiring),
    Source("Greenhouse", source_greenhouse),
    Source("Lever", source_lever),

    # Europe.
    Source("EURES", source_eures),
    Source("France Travail", source_france_travail),
    Source("JobsIreland", source_jobsireland),
    Source("European job boards", source_european_portals),
]


def deduplicate_jobs(jobs: Iterable[dict]) -> list[dict]:
    result = []
    seen = set()
    for job in jobs:
        key = job_id(job)
        if key in seen:
            continue
        seen.add(key)
        result.append(job)
    return result


def collect_all() -> list[dict]:
    print("\n🔍 Fetching jobs…")
    all_records = []
    for source in SOURCES:
        if not source.enabled:
            print(f"  {source.name}: disabled")
            continue
        all_records.extend(safe_source_call(source.name, source.fn))

    records = deduplicate_jobs(all_records)
    records.sort(key=lambda x: (bool(x.get("discovery_only")), -(x.get("posted_at") or 0)))
    print(f"\n  Raw records: {len(all_records)}")
    print(f"  Unique records: {len(records)}")
    return records


# ============================================================================
# TELEGRAM
# ============================================================================

def require_telegram() -> None:
    missing = [x for x, value in [("TG_TOKEN", TG_TOKEN), ("TG_CHAT_ID", TG_CHAT_ID)] if not value]
    if missing:
        raise RuntimeError("Missing Telegram environment variable(s): " + ", ".join(missing))


def tg_send(text: str, url: str | None = None) -> bool:
    require_telegram()
    payload: dict[str, Any] = {
        "chat_id": TG_CHAT_ID,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }
    if url and url.startswith(("http://", "https://")):
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "Open / Apply →", "url": url}]]}
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode())
        if not result.get("ok"):
            print(f"  [WARN] Telegram: {result.get('description', 'unknown error')}")
            return False
        return True
    except Exception as exc:
        print(f"  [WARN] Telegram send failed: {exc}")
        return False


def format_card(job: dict, index: int, total: int) -> str:
    timestamp = job.get("posted_at") or 0
    posted = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%d %b %Y") if timestamp else "—"
    family = job.get("job_family") or get_job_family(job)
    tags = " · ".join(str(x)[:25] for x in (job.get("tags") or [])[:4])
    lines = [
        f"[{index}/{total}] {job.get('title') or 'Untitled'}",
        f"Track    : {family}",
        f"Company  : {job.get('company') or '—'}",
        f"Source   : {job.get('source') or '—'}",
        f"Location : {job.get('location') or 'Remote'}",
        f"Type     : {get_work_type(job)}",
        f"Posted   : {posted}",
    ]
    if family in {"Frontend", "Software Engineering", "Solution / Software Architecture"}:
        lines.append("Interview: no live-coding signal ✓")
    if tags:
        lines.append(f"Tags     : {tags}")
    return "\n".join(lines)


def format_portal_card(job: dict, index: int, total: int) -> str:
    return "\n".join([
        f"[Board {index}/{total}] {job['source']}",
        f"Track    : {job['job_family']}",
        "Type     : Official live search",
        f"Search   : {job['title'].split(' — ', 1)[-1]}",
    ])


def send_digest(jobs: list[dict], portals: list[dict]) -> None:
    sendable = jobs[:DAILY_LIMIT]
    family_counts = Counter(job.get("job_family", "Other") for job in sendable)
    source_counts = Counter(job.get("source", "Unknown") for job in sendable)
    now = datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M UTC")

    summary = " | ".join(f"{k}: {v}" for k, v in family_counts.items()) or "No qualifying vacancies"
    source_summary = " | ".join(f"{k} ({v})" for k, v in source_counts.most_common(5)) or "—"

    header = "\n".join([
        f"⚡ {len(sendable)} new jobs — {now}",
        summary,
        "",
        f"Sources: {source_summary}",
        "Mid-level + senior architecture/software · Frontend any level · Customer care English/Yoruba only",
    ])

    if not tg_send(header):
        return
    time.sleep(0.5)

    sent = 0
    for i, job in enumerate(sendable, 1):
        if tg_send(format_card(job, i, len(sendable)), job.get("url")):
            sent += 1
        time.sleep(0.35)

    if portals:
        time.sleep(0.5)
        tg_send("🌍 European & national job boards\nOfficial live search links. They do not consume your daily vacancy limit.")
        time.sleep(0.4)
        for i, portal in enumerate(portals, 1):
            tg_send(format_portal_card(portal, i, len(portals)), portal.get("url"))
            time.sleep(0.2)

    tg_send(f"✅ {sent}/{len(sendable)} vacancy cards sent.\n📋 Daily vacancy limit: {DAILY_LIMIT}")


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    print("=" * 76)
    print("🚀 Remote Job Alert — Telegram")
    print("=" * 76)
    records = collect_all()

    actual_jobs = [x for x in records if not x.get("discovery_only")]
    portals = [x for x in records if x.get("discovery_only")]
    seen = load_seen()

    new_jobs = [x for x in actual_jobs if job_id(x) not in seen]
    new_jobs.sort(key=lambda x: x.get("posted_at") or 0, reverse=True)

    print(f"  🆕 New unseen vacancies: {len(new_jobs)}")
    print(f"  🌍 European portal search links: {len(portals)}")

    to_send = new_jobs[:DAILY_LIMIT]
    if len(new_jobs) > DAILY_LIMIT:
        print(f"  📋 Held for next run: {len(new_jobs) - DAILY_LIMIT}")

    send_digest(to_send, portals)

    # Only mark vacancies actually selected for sending as seen.
    seen.update(job_id(x) for x in to_send)
    if len(seen) > 5000:
        seen = set(sorted(seen)[-5000:])
    save_seen(seen)
    print(f"  📲 Done — {len(to_send)} vacancy cards selected for Telegram.")


if __name__ == "__main__":
    main()
