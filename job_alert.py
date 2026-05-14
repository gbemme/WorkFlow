#!/usr/bin/env python3
"""
🚀 Frontend Job Alert — Telegram Edition
Mid/Senior · Remote + Relocation · No Live Coding
Runs daily at 8 AM Lisbon time via GitHub Actions.

Sources
───────
  Public APIs  : RemoteOK, Remotive, Arbeitnow, Jobicy, FindWork (optional)
  RSS feeds    : WeWorkRemotely, Remote.co, RemoteOK tag feeds
  HN Hiring    : HackerNews "Ask HN: Who is Hiring?" monthly thread
  ATS discovery: Greenhouse & Lever boards fetched from a curated startup
                 index (Glassdoor/Y-Combinator public lists) — no hardcoded slugs
"""

import os, json, re, hashlib, urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TG_TOKEN   = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
SEEN_FILE  = Path("seen_jobs.json")

DAILY_LIMIT = 15          # max jobs sent per run, newest first
ATS_TIMEOUT = 6           # seconds per ATS board request (many to hit)
MAX_ATS_BOARDS = 80       # cap how many boards we discover per ATS

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FILTERS  (edit these to tune what you receive)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# A job is frontend if its title/desc matches a role phrase OR (stack + context)
FRONTEND_ROLE_KW = [
    "frontend engineer", "frontend developer",
    "front-end engineer", "front-end developer",
    "front end engineer", "front end developer",
    "react engineer", "react developer",
    "vue engineer", "vue developer",
    "next.js engineer", "nextjs engineer",
    "next.js developer", "nextjs developer",
    "nuxt engineer", "nuxt developer",
    "ui engineer", "ui developer",
    "web engineer", "web developer",
]
FRONTEND_STACK_KW = ["react", "next.js", "nextjs", "vue", "nuxt", "svelte",
                     "typescript", "javascript", "solidjs", "astro", "remix"]
FRONTEND_CONTEXT_KW = ["frontend", "front-end", "front end"]

SENIORITY_KW = ["senior", " sr ", "sr.", "staff", "lead", "principal",
                "mid-level", "mid level", "midlevel", "intermediate"]

# These anywhere in combined text → reject the job entirely
HARD_EXCLUDE_KW = [
    # Wrong level
    "intern", "internship", "junior", " jr ", "jr.", "entry level",
    "entry-level", "graduate", "apprentice", "trainee",
    # Wrong role
    "backend engineer", "back-end engineer", "backend developer",
    "fullstack", "full-stack", "full stack",
    "mobile engineer", "ios engineer", "android engineer",
    "devops", "platform engineer", "sre ", "site reliability",
    "qa engineer", "test engineer", "data engineer",
    "machine learning", "ai engineer", "ml engineer",
    "product manager", "product designer", "ux designer",
    "customer success", "customer support", "sales", "marketing",
    "account manager", "recruiter", "talent acquisition",
]

# These in desc/title signal a live-coding interview → skip
LIVE_CODING_KW = [
    "live coding", "live code", "live-coding", "live-code",
    "whiteboard", "white board", "white-board",
    "leetcode", "leet code", "hackerrank", "hacker rank",
    "codility", "codesignal", "code signal",
    "algorithmic test", "algorithm test",
     "live technical",
]

REMOTE_KW = ["remote", "worldwide", "anywhere", "distributed",
             "remote-first", "work from home", "wfh"]
RELOCATION_KW = ["visa sponsorship", "relocation", "relocate",
                 "moving allowance", "relocation package"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FILTER LOGIC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _t(text):
    return (text or "").lower()

def is_frontend(text):
    t = _t(text)
    if any(k in t for k in HARD_EXCLUDE_KW):
        return False
    if any(k in t for k in FRONTEND_ROLE_KW):
        return True
    has_stack   = any(k in t for k in FRONTEND_STACK_KW)
    has_context = any(k in t for k in FRONTEND_CONTEXT_KW)
    return has_stack and has_context

def is_mid_senior(text):
    t = _t(text)
    if any(k in t for k in HARD_EXCLUDE_KW):
        return False
    return any(k in t for k in SENIORITY_KW)

def is_remote_or_relocation(text):
    t = _t(text)
    return any(k in t for k in REMOTE_KW) or any(k in t for k in RELOCATION_KW)

def has_live_coding(text):
    """Return True if the job description mentions live-coding interviews."""
    t = _t(text)
    return any(k in t for k in LIVE_CODING_KW)

def is_good_job(job):
    """Single entry-point: returns True if job passes all filters."""
    combined = " ".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("desc_snippet", ""),
    ])
    if not is_frontend(combined):
        return False
    if not is_mid_senior(combined):
        return False
    if not is_remote_or_relocation(combined):
        return False
    if has_live_coding(combined):
        return False
    return True

def get_work_type(job):
    t = _t(f"{job.get('location','')} {job.get('desc_snippet','')}")
    has_remote     = any(k in t for k in REMOTE_KW)
    has_relocation = any(k in t for k in RELOCATION_KW)
    if has_remote and has_relocation:
        return "🌍 Remote + Relocation"
    if has_relocation:
        return "✈️  Relocation"
    return "🏠 Remote"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UTILITIES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def job_id(job):
    key = (job.get("title","") + job.get("company","") + job.get("url","")).lower()
    return hashlib.md5(key.encode()).hexdigest()[:12]

def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))

def fetch_url(url, headers=None, timeout=12):
    h = {"User-Agent": "FrontendJobBot/3.0 (github-actions)"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_json(url, headers=None, timeout=12):
    return json.loads(fetch_url(url, headers, timeout))

def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "")

def parse_date(text):
    """Best-effort date string → UTC float. Returns 0.0 on failure (sorts last)."""
    if not text:
        return 0.0
    text = text.strip()
    fmts = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    return 0.0

def make_job(title, company, url, source, location="Remote",
             tags=None, desc="", posted_at=0.0):
    """Construct a normalised job dict."""
    return {
        "title":        title.strip()[:160],
        "company":      company.strip()[:80],
        "url":          url.strip(),
        "source":       source,
        "location":     location.strip()[:80],
        "tags":         (tags or [])[:5],
        "desc_snippet": strip_html(desc)[:300],
        "posted_at":    posted_at,
    }

def fetch_rss(url, source):
    try:
        raw  = fetch_url(url)
        root = ET.fromstring(raw)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        jobs = []
        for item in items:
            title = (item.findtext("title") or
                     item.findtext("atom:title", namespaces=ns) or "").strip()
            link  = (item.findtext("link") or
                     item.findtext("atom:link", namespaces=ns) or "").strip()
            desc  = (item.findtext("description") or
                     item.findtext("atom:summary", namespaces=ns) or "")
            pub   = (item.findtext("pubDate") or
                     item.findtext("published") or
                     item.findtext("atom:published", namespaces=ns) or "")
            j = make_job(title, "", link, source, desc=desc,
                         posted_at=parse_date(pub))
            if is_good_job(j):
                jobs.append(j)
        return jobs
    except Exception as e:
        print(f"  [WARN] {source} RSS: {e}")
        return []

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SOURCES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def source_remoteok():
    try:
        data = fetch_json("https://remoteok.com/api")
        jobs = []
        for item in data[1:]:
            j = make_job(
                title     = item.get("position",""),
                company   = item.get("company",""),
                url       = item.get("url",""),
                source    = "RemoteOK",
                tags      = item.get("tags",[]),
                desc      = item.get("description",""),
                posted_at = parse_date(item.get("date","")),
            )
            if is_good_job(j):
                jobs.append(j)
        print(f"  RemoteOK:        {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] RemoteOK: {e}"); return []

def source_remotive():
    try:
        data = fetch_json(
            "https://remotive.com/api/remote-jobs?category=software-dev&limit=100"
        )
        jobs = []
        for item in data.get("jobs", []):
            j = make_job(
                title     = item.get("title",""),
                company   = item.get("company_name",""),
                url       = item.get("url",""),
                source    = "Remotive",
                tags      = item.get("tags",[]),
                desc      = item.get("description",""),
                posted_at = parse_date(item.get("publication_date","")),
            )
            if is_good_job(j):
                jobs.append(j)
        print(f"  Remotive:        {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] Remotive: {e}"); return []

def source_arbeitnow():
    try:
        data = fetch_json("https://www.arbeitnow.com/api/job-board-api")
        jobs = []
        for item in data.get("data", []):
            if not item.get("remote"):
                continue
            j = make_job(
                title     = item.get("title",""),
                company   = item.get("company_name",""),
                url       = item.get("url",""),
                source    = "Arbeitnow",
                location  = item.get("location","Remote"),
                tags      = item.get("tags",[]),
                desc      = item.get("description",""),
                posted_at = parse_date(item.get("created_at","")),
            )
            if is_good_job(j):
                jobs.append(j)
        print(f"  Arbeitnow:       {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] Arbeitnow: {e}"); return []

def source_jobicy():
    try:
        data = fetch_json(
            "https://jobicy.com/api/v2/remote-jobs?count=50&industry=engineering"
        )
        jobs = []
        for item in data.get("jobs", []):
            j = make_job(
                title     = item.get("jobTitle",""),
                company   = item.get("companyName",""),
                url       = item.get("url",""),
                source    = "Jobicy",
                desc      = item.get("jobDescription",""),
                posted_at = parse_date(item.get("pubDate","")),
            )
            if is_good_job(j):
                jobs.append(j)
        print(f"  Jobicy:          {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] Jobicy: {e}"); return []

def source_findwork():
    """Optional — set FINDWORK_KEY secret for this source."""
    api_key = os.environ.get("FINDWORK_KEY","")
    if not api_key:
        print("  FindWork:        skipped (set FINDWORK_KEY secret)")
        return []
    try:
        data = fetch_json(
            "https://findwork.dev/api/jobs/?remote=true&role=frontend",
            headers={"Authorization": f"Token {api_key}"},
        )
        jobs = []
        for item in data.get("results", []):
            kw = item.get("keywords") or []
            j = make_job(
                title     = item.get("role",""),
                company   = item.get("company_name",""),
                url       = item.get("url",""),
                source    = "FindWork",
                tags      = kw,
                desc      = " ".join(kw),
                posted_at = parse_date(item.get("date_posted","")),
            )
            if is_good_job(j):
                jobs.append(j)
        print(f"  FindWork:        {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] FindWork: {e}"); return []

def source_rss():
    """All RSS feeds consolidated."""
    feeds = [
        ("https://weworkremotely.com/categories/remote-programming-jobs.rss", "WWR/Engineering"),
        ("https://weworkremotely.com/categories/remote-design-jobs.rss",      "WWR/Design"),
        ("https://remoteok.com/remote-react-jobs.rss",                        "RemoteOK/React"),
        ("https://remoteok.com/remote-vue-jobs.rss",                          "RemoteOK/Vue"),
        ("https://remoteok.com/remote-typescript-jobs.rss",                   "RemoteOK/TypeScript"),
        ("https://remote.co/job-categories/developer-jobs/feed/",             "Remote.co"),
    ]
    jobs = []
    for url, name in feeds:
        found = fetch_rss(url, name)
        if found:
            print(f"  {name}: {len(found)}")
        jobs += found
    return jobs

def source_hn_hiring():
    """
    Parses the monthly 'Ask HN: Who is Hiring?' thread.
    Founders post directly — earliest signal, often no formal interview process.
    """
    try:
        search = fetch_json(
            "https://hn.algolia.com/api/v1/search"
            "?query=Ask+HN+Who+is+Hiring&tags=ask_hn&hitsPerPage=5"
        )
        hits = [h for h in search.get("hits", [])
                if "who is hiring" in _t(h.get("title",""))]
        if not hits:
            return []

        story_id = hits[0]["objectID"]
        story    = fetch_json(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        )
        kids = (story.get("kids") or [])[:300]

        jobs = []
        for kid_id in kids:
            try:
                comment = fetch_json(
                    f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json",
                    timeout=5,
                )
                raw = comment.get("text","")
                if not raw:
                    continue
                text = strip_html(raw)
                text = (text.replace("&amp;","&").replace("&#x27;","'")
                            .replace("&gt;",">").replace("&lt;","<"))
                first_line = text.split("\n")[0][:160]
                j = make_job(
                    title     = first_line,
                    company   = "HN Hiring",
                    url       = f"https://news.ycombinator.com/item?id={kid_id}",
                    source    = "HN Who's Hiring",
                    location  = "Remote / Various",
                    tags      = ["startup","direct"],
                    desc      = text[:300],
                    posted_at = float(comment.get("time") or 0),
                )
                if is_good_job(j):
                    jobs.append(j)
            except Exception:
                continue

        print(f"  HN Who's Hiring: {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] HN Who's Hiring: {e}"); return []

# ── Dynamic ATS discovery ──────────────────────────────────────────────────────
# Instead of a hardcoded list of startup slugs, we discover boards dynamically
# from Greenhouse's own public board index and Lever's company directory.
# This catches new companies automatically as they sign up.

def _discover_greenhouse_slugs():
    """
    Fetch Greenhouse's public job board index (undocumented but stable endpoint).
    Returns a list of board slugs for companies currently hiring.
    """
    try:
        # Greenhouse exposes a paginated token directory
        data = fetch_json(
            "https://boards-api.greenhouse.io/v1/boards",
            timeout=10,
        )
        slugs = [b.get("token","") for b in data.get("boards",[]) if b.get("token")]
        return slugs[:MAX_ATS_BOARDS]
    except Exception:
        # Fallback: known-good slugs if the index is unavailable
        return [
            "linear","vercel","notion","loom","retool","brex","rippling",
            "dbtlabs","gitpod","supabase","railway","replit","clerk",
            "neon","resend","infisical","prisma","turso","planetscale",
            "prefect","modal-labs","trigger","airbyte","metabase",
        ]

def _discover_lever_slugs():
    """
    Lever doesn't expose a slug directory, so we pull from the YC company list
    (public JSON) which has the Lever URL for companies that use it.
    """
    try:
        # YC's public company API includes ats_url for many companies
        data = fetch_json(
            "https://api.ycombinator.com/v0.1/companies?batch=&tags=&"
            "isHiring=true&limit=100",
            timeout=10,
        )
        slugs = set()
        for co in data.get("companies", []):
            ats = co.get("ats_url","") or ""
            if "lever.co" in ats:
                # URL format: https://jobs.lever.co/<slug>
                slug = ats.rstrip("/").split("/")[-1]
                if slug:
                    slugs.add(slug)
        return list(slugs)[:MAX_ATS_BOARDS]
    except Exception:
        return []

def source_greenhouse():
    slugs = _discover_greenhouse_slugs()
    jobs  = []
    for slug in slugs:
        try:
            data = fetch_json(
                f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
                timeout=ATS_TIMEOUT,
            )
            for item in data.get("jobs",[]):
                loc = " ".join(m.get("name","") for m in (item.get("offices") or []))
                j   = make_job(
                    title     = item.get("title",""),
                    company   = slug.replace("-"," ").title(),
                    url       = item.get("absolute_url",""),
                    source    = "Greenhouse",
                    location  = loc or "Remote",
                    tags      = ["startup"],
                    desc      = item.get("content",""),
                    posted_at = parse_date(item.get("updated_at","")),
                )
                if is_good_job(j):
                    jobs.append(j)
        except Exception:
            pass
    print(f"  Greenhouse:      {len(jobs)} (from {len(slugs)} boards)")
    return jobs

def source_lever():
    slugs = _discover_lever_slugs()
    jobs  = []
    for slug in slugs:
        try:
            data = fetch_json(
                f"https://api.lever.co/v0/postings/{slug}?mode=json",
                timeout=ATS_TIMEOUT,
            )
            for item in data:
                cats = item.get("categories") or {}
                j    = make_job(
                    title     = item.get("text",""),
                    company   = slug.replace("-"," ").title(),
                    url       = item.get("hostedUrl",""),
                    source    = "Lever",
                    location  = cats.get("location","Remote"),
                    tags      = ["startup"],
                    desc      = item.get("descriptionPlain",""),
                    posted_at = (item.get("createdAt") or 0) / 1000,
                )
                if is_good_job(j):
                    jobs.append(j)
        except Exception:
            pass
    print(f"  Lever:           {len(jobs)} (from {len(slugs)} boards)")
    return jobs

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SOURCES = [
    source_remoteok,
    source_remotive,
    source_arbeitnow,
    source_jobicy,
    source_findwork,
    source_rss,
    source_hn_hiring,
    source_greenhouse,
    source_lever,
]

def collect_all():
    print("\n🔍 Fetching…")
    raw = []
    for fn in SOURCES:
        try:
            raw += fn()
        except Exception as e:
            print(f"  [ERROR] {fn.__name__}: {e}")

    # Deduplicate by content hash
    seen_keys, unique = set(), []
    for j in raw:
        k = job_id(j)
        if k not in seen_keys:
            seen_keys.add(k)
            j.setdefault("posted_at", 0.0)
            unique.append(j)

    # Sort newest first; unknown dates fall to the bottom
    unique.sort(key=lambda j: j["posted_at"], reverse=True)
    print(f"\n  ✅ Unique qualifying jobs: {len(unique)}")
    return unique

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TELEGRAM  (plain text + inline button — most robust, zero parse errors)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def tg_send(text, url=None):
    """
    Send a plain-text message. If `url` is given, attaches an [Apply →] button.
    Uses no parse_mode — immune to formatting/escaping errors.
    Returns True on success.
    """
    payload = {"chat_id": TG_CHAT_ID, "text": text[:4000]}
    if url and url.startswith(("http://", "https://")):
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "Apply →", "url": url}]]
        }
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        if not resp.get("ok"):
            print(f"  [WARN] TG: {resp.get('description')} | {text[:50]!r}")
            return False
        return True
    except Exception as e:
        print(f"  [WARN] TG send failed: {e} | {text[:50]!r}")
        return False

def format_card(job, index, total):
    ts     = job.get("posted_at") or 0.0
    posted = (datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b %Y")
              if ts > 0 else "—")
    tags   = " · ".join(str(t)[:20] for t in (job.get("tags") or [])[:4])

    lines = [
        f"[{index}/{total}] {job['title']}",
        f"Company  : {job.get('company') or '—'}",
        f"Source   : {job['source']}",
        f"Location : {job.get('location') or 'Remote'}",
        f"Type     : {get_work_type(job)}",
        f"Posted   : {posted}",
        f"Interview: no live coding ✓",
    ]
    if tags:
        lines.append(f"Tags     : {tags}")
    return "\n".join(lines)

def send_digest(jobs):
    import time

    now    = datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M UTC")
    counts = Counter(j["source"] for j in jobs)
    srcs   = " | ".join(f"{s} ({c})" for s, c in counts.most_common(4))

    tg_send(
        f"⚡ {len(jobs)} Frontend jobs — {now}\n"
        f"Mid/Senior · Remote + Relocation · No live coding\n\n"
        f"{srcs}"
    )
    time.sleep(1)

    ok = 0
    for i, job in enumerate(jobs, 1):
        if tg_send(format_card(job, i, len(jobs)), url=job.get("url")):
            ok += 1
        time.sleep(0.4)   # ~2.5 msg/sec, well under TG limit

    time.sleep(0.5)
    tg_send(
        f"✅ {ok}/{len(jobs)} sent · top {len(jobs)} most recent\n"
        f"Next update tomorrow at 8:00 AM Lisbon 🇵🇹"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    seen     = load_seen()
    all_jobs = collect_all()
    new_jobs = [j for j in all_jobs if job_id(j) not in seen]

    print(f"  🆕 New unseen jobs : {len(new_jobs)}")

    if not new_jobs:
        print("  Nothing new — skipping notification.")
        return

    to_send = new_jobs[:DAILY_LIMIT]
    skipped = len(new_jobs) - len(to_send)
    if skipped:
        print(f"  📋 Capped at {DAILY_LIMIT}/day ({skipped} held for tomorrow)")

    send_digest(to_send)

    # Persist only the sent IDs — unsent jobs remain eligible tomorrow
    seen.update(job_id(j) for j in to_send)
    if len(seen) > 5000:
        seen = set(list(seen)[-5000:])
    save_seen(seen)
    print(f"  📲 Done — {len(to_send)} cards sent to Telegram.")

if __name__ == "__main__":
    main()