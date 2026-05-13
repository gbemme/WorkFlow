#!/usr/bin/env python3
"""
🚀 Frontend Job Alert — Telegram Edition
Mid/Senior · Remote + Relocation · Multi-Source
Runs daily at 8 AM Lisbon time via GitHub Actions.
Sends Telegram messages only for NEW unseen jobs.
Seen jobs cached in seen_jobs.json (committed back to repo).

Sources:
  - RemoteOK API
  - WeWorkRemotely RSS
  - Remotive API
  - Arbeitnow API
  - Jobicy API
  - FindWork API (optional key)
  - HackerNews Who's Hiring (monthly thread)
  - Greenhouse startup ATS boards (direct, not on aggregators)
  - Lever startup ATS boards (direct)
  - Extra RSS (Remote.co, JobsForRemotes, RemoteOK tag feeds)
"""

import os, json, re, hashlib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
TG_TOKEN   = os.environ["TG_TOKEN"]    # BotFather token
TG_CHAT_ID = os.environ["TG_CHAT_ID"]  # your personal chat ID or group ID
SEEN_FILE  = Path("seen_jobs.json")

# ── Keyword lists ──────────────────────────────────────────────────────────────
FRONTEND_KW = [
    "frontend", "front-end", "front end", "ui engineer", "ui developer",
    "web engineer", "web developer", "react", "vue", "angular", "svelte",
    "nextjs", "next.js", "nuxt", "typescript", "javascript", "ember",
    "solidjs", "remix", "astro", "qwik",
]
SENIORITY_KW = [
    "senior", "sr.", "sr ", "lead", "principal", "staff",
    "mid-level", "mid level", "midlevel", "intermediate", " iii", " ii",
]
EXCLUDE_KW = [
    "intern", "internship", "junior", "jr.", "jr ",
    "entry level", "entry-level", "graduate", "apprentice", "trainee",
]
REMOTE_KW = [
    "remote", "distributed", "work from home", "wfh", "anywhere",
    "fully remote", "100% remote",
]
RELOCATION_KW = [
    "relocation", "relocate", "visa", "visa sponsorship", "sponsorship",
    "moving allowance", "relocation package", "relocation assistance",
    "moving support", "help you move",
]

# ── Filters ────────────────────────────────────────────────────────────────────
def is_frontend(text):
    t = text.lower()
    return any(k in t for k in FRONTEND_KW)

def is_mid_senior(text):
    t = text.lower()
    if any(k in t for k in EXCLUDE_KW):
        return False
    # No level info in text → include (startups often skip it)
    return True

def is_remote_or_relocation(text):
    t = text.lower()
    return any(k in t for k in REMOTE_KW) or any(k in t for k in RELOCATION_KW)

def get_work_type(text):
    """Return emoji label for work arrangement."""
    t = text.lower()
    has_remote     = any(k in t for k in REMOTE_KW)
    has_relocation = any(k in t for k in RELOCATION_KW)
    if has_remote and has_relocation:
        return "🌍 Remote + Relocation"
    if has_relocation:
        return "✈️ Relocation"
    if has_remote:
        return "🏠 Remote"
    return "🌐 Remote"  # all jobs here are at least remote-flagged

# ── Helpers ────────────────────────────────────────────────────────────────────
def job_id(job):
    key = (job.get("title","") + job.get("company","") + job.get("url","")).lower()
    return hashlib.md5(key.encode()).hexdigest()[:12]

def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))

def fetch_url(url, headers=None, timeout=15):
    h = {"User-Agent": "FrontendJobBot/2.0 (github-actions)"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_json(url, headers=None):
    return json.loads(fetch_url(url, headers))

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
                     item.findtext("atom:summary", namespaces=ns) or "").strip()
            combined = f"{title} {desc} remote"
            if is_frontend(combined) and is_mid_senior(combined):
                jobs.append({"title": title, "company": "", "url": link,
                             "tags": [], "source": source,
                             "location": "Remote", "desc_snippet": desc[:200]})
        return jobs
    except Exception as e:
        print(f"  [WARN] {source} RSS: {e}")
        return []

# ── Sources ────────────────────────────────────────────────────────────────────

def source_remoteok():
    try:
        data = fetch_json("https://remoteok.com/api")
        jobs = []
        for item in data[1:]:
            title   = item.get("position", "")
            company = item.get("company", "")
            tags    = " ".join(item.get("tags") or [])
            desc    = item.get("description", "")
            combined = f"{title} {tags} {desc} remote"
            if is_frontend(combined) and is_mid_senior(combined):
                jobs.append({
                    "title": title, "company": company,
                    "url": item.get("url",""),
                    "tags": (item.get("tags") or [])[:5],
                    "source": "RemoteOK", "location": "Remote",
                    "desc_snippet": desc[:200],
                })
        print(f"  RemoteOK:              {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] RemoteOK: {e}"); return []

def source_weworkremotely():
    jobs = []
    for url, name in [
        ("https://weworkremotely.com/categories/remote-programming-jobs.rss", "WWR/Engineering"),
        ("https://weworkremotely.com/categories/remote-design-jobs.rss",      "WWR/Design"),
    ]:
        j = fetch_rss(url, name)
        print(f"  {name}: {len(j)}")
        jobs += j
    return jobs

def source_remotive():
    try:
        data = fetch_json("https://remotive.com/api/remote-jobs?category=software-dev&limit=100")
        jobs = []
        for item in data.get("jobs", []):
            title   = item.get("title","")
            company = item.get("company_name","")
            desc    = item.get("description","")
            if is_frontend(f"{title} {desc}") and is_mid_senior(f"{title} {desc}"):
                jobs.append({
                    "title": title, "company": company,
                    "url": item.get("url",""),
                    "tags": (item.get("tags") or [])[:5],
                    "source": "Remotive", "location": "Remote",
                    "desc_snippet": re.sub(r"<[^>]+>","",desc)[:200],
                })
        print(f"  Remotive:              {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] Remotive: {e}"); return []

def source_arbeitnow():
    try:
        data = fetch_json("https://www.arbeitnow.com/api/job-board-api")
        jobs = []
        for item in data.get("data", []):
            title   = item.get("title","")
            company = item.get("company_name","")
            desc    = item.get("description","")
            loc     = item.get("location","")
            remote  = item.get("remote", False)
            combined = f"{title} {desc} {loc}"
            if not (remote or is_remote_or_relocation(combined)):
                continue
            if is_frontend(combined) and is_mid_senior(combined):
                jobs.append({
                    "title": title, "company": company,
                    "url": item.get("url",""),
                    "tags": (item.get("tags") or [])[:5],
                    "source": "Arbeitnow", "location": loc or "Remote",
                    "desc_snippet": re.sub(r"<[^>]+>","",desc)[:200],
                })
        print(f"  Arbeitnow:             {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] Arbeitnow: {e}"); return []

def source_jobicy():
    try:
        data = fetch_json("https://jobicy.com/api/v2/remote-jobs?count=50&industry=engineering")
        jobs = []
        for item in data.get("jobs", []):
            title   = item.get("jobTitle","")
            company = item.get("companyName","")
            desc    = item.get("jobDescription","")
            if is_frontend(f"{title} {desc}") and is_mid_senior(f"{title} {desc}"):
                jobs.append({
                    "title": title, "company": company,
                    "url": item.get("url",""), "tags": [],
                    "source": "Jobicy", "location": "Remote",
                    "desc_snippet": re.sub(r"<[^>]+>","",desc)[:200],
                })
        print(f"  Jobicy:                {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] Jobicy: {e}"); return []

def source_findwork():
    api_key = os.environ.get("FINDWORK_KEY","")
    if not api_key:
        print("  FindWork:              skipped (add FINDWORK_KEY secret)")
        return []
    try:
        data = fetch_json(
            "https://findwork.dev/api/jobs/?remote=true&role=frontend",
            headers={"Authorization": f"Token {api_key}"}
        )
        jobs = []
        for item in data.get("results", []):
            title   = item.get("role","")
            company = item.get("company_name","")
            kw      = " ".join(item.get("keywords") or [])
            if is_frontend(f"{title} {kw}") and is_mid_senior(f"{title} {kw}"):
                jobs.append({
                    "title": title, "company": company,
                    "url": item.get("url",""),
                    "tags": (item.get("keywords") or [])[:5],
                    "source": "FindWork", "location": "Remote",
                    "desc_snippet": "",
                })
        print(f"  FindWork:              {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] FindWork: {e}"); return []

def source_hn_whoishiring():
    """Founders post directly — earliest signal for new roles."""
    try:
        search = fetch_json(
            "https://hn.algolia.com/api/v1/search"
            "?query=Ask+HN+Who+is+Hiring&tags=ask_hn&hitsPerPage=5"
        )
        hits = [h for h in search.get("hits",[])
                if "who is hiring" in h.get("title","").lower()]
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
                    f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json"
                )
                text = comment.get("text","")
                if not text:
                    continue
                clean = re.sub(r"<[^>]+>","", text)
                clean = (clean.replace("&amp;","&").replace("&#x27;","'")
                              .replace("&gt;",">").replace("&lt;","<"))
                snippet = clean[:600]
                if not is_frontend(snippet):
                    continue
                if not is_mid_senior(snippet):
                    continue
                if not is_remote_or_relocation(snippet):
                    continue
                first_line = clean.split("\n")[0][:120]
                jobs.append({
                    "title": first_line, "company": "HN Hiring",
                    "url": f"https://news.ycombinator.com/item?id={kid_id}",
                    "tags": ["startup","direct"],
                    "source": "HN Who's Hiring", "location": "Remote/Various",
                    "desc_snippet": snippet[:200],
                })
            except:
                continue
        print(f"  HN Who's Hiring:       {len(jobs)}")
        return jobs
    except Exception as e:
        print(f"  [WARN] HN Who's Hiring: {e}"); return []

def source_greenhouse_startups():
    """Direct ATS boards — these don't surface on aggregators."""
    startups = [
        "linear","vercel","notion","loom","retool","brex",
        "rippling","dbtlabs","gitpod","supabase","planetscale",
        "railway","replit","modal-labs","prefect","clerk",
        "neon","resend","trigger","infisical",
    ]
    jobs = []
    for slug in startups:
        try:
            data = fetch_json(
                f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
            )
            for item in data.get("jobs",[]):
                title = item.get("title","")
                loc   = " ".join(m.get("name","") for m in (item.get("offices") or []))
                desc  = item.get("content","")
                combined = f"{title} {loc} {desc} remote"
                if is_frontend(combined) and is_mid_senior(title):
                    jobs.append({
                        "title": title, "company": slug.title(),
                        "url": item.get("absolute_url",""),
                        "tags": ["startup"],
                        "source": f"Greenhouse/{slug}",
                        "location": loc or "Remote",
                        "desc_snippet": re.sub(r"<[^>]+>","",desc)[:200],
                    })
        except:
            pass
    print(f"  Greenhouse startups:   {len(jobs)}")
    return jobs

def source_lever_startups():
    """Direct Lever ATS boards."""
    startups = [
        "vercel","linear","loom","retool","dbt",
        "clerk","neon","turso","infisical","prisma",
    ]
    jobs = []
    for slug in startups:
        try:
            data = fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            for item in data:
                title = item.get("text","")
                cats  = item.get("categories") or {}
                loc   = cats.get("location","")
                desc  = (item.get("descriptionPlain") or "")[:200]
                combined = f"{title} {loc} {desc} remote"
                if is_frontend(combined) and is_mid_senior(title):
                    jobs.append({
                        "title": title, "company": slug.title(),
                        "url": item.get("hostedUrl",""),
                        "tags": ["startup"],
                        "source": f"Lever/{slug}",
                        "location": loc or "Remote",
                        "desc_snippet": desc,
                    })
        except:
            pass
    print(f"  Lever startups:        {len(jobs)}")
    return jobs

def source_rss_extra():
    feeds = [
        ("https://remoteok.com/remote-react-jobs.rss",      "RemoteOK/React"),
        ("https://remoteok.com/remote-vue-jobs.rss",         "RemoteOK/Vue"),
        ("https://remoteok.com/remote-typescript-jobs.rss",  "RemoteOK/TS"),
        ("https://remote.co/job-categories/developer-jobs/feed/", "Remote.co"),
        ("https://jobsforremotes.com/feed/",                 "JobsForRemotes"),
    ]
    jobs = []
    for url, name in feeds:
        j = fetch_rss(url, name)
        if j:
            print(f"  {name}: {len(j)}")
        jobs += j
    return jobs

# ── Collect all ────────────────────────────────────────────────────────────────

def collect_all():
    print("\n🔍 Fetching from all sources…")
    all_jobs = []
    for fn in [
        source_remoteok, source_weworkremotely, source_remotive,
        source_arbeitnow, source_jobicy, source_findwork,
        source_hn_whoishiring, source_greenhouse_startups,
        source_lever_startups, source_rss_extra,
    ]:
        try:
            all_jobs += fn()
        except Exception as e:
            print(f"  [ERROR] {fn.__name__}: {e}")

    seen_keys, unique = set(), []
    for j in all_jobs:
        k = job_id(j)
        if k not in seen_keys:
            seen_keys.add(k)
            unique.append(j)

    print(f"\n  ✅ Total unique this run: {len(unique)}")
    return unique

# ── Telegram sender ────────────────────────────────────────────────────────────

def tg_escape(text):
    """Escape special chars for Telegram MarkdownV2."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text

def send_telegram(text):
    """Send a single Telegram message (MarkdownV2, up to 4096 chars)."""
    url     = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id":    TG_CHAT_ID,
        "text":       text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read())
    if not resp.get("ok"):
        print(f"  [WARN] Telegram error: {resp}")

def send_summary(jobs):
    """
    Send one summary header + individual job cards.
    Batches cards to avoid hitting Telegram rate limits (30 msg/sec).
    """
    import time

    now     = datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M UTC")
    counts  = Counter(j["source"] for j in jobs)
    top_src = ", ".join(f"{s} \\({c}\\)" for s, c in counts.most_common(5))

    # ── Summary header ──────────────────────────────────────────────────────────
    header = (
        f"⚡ *{tg_escape(str(len(jobs)))} new Frontend jobs* — {tg_escape(now)}\n"
        f"🎯 Mid/Senior · Remote \\+ Relocation\n\n"
        f"*Top sources:* {top_src}\n"
        f"{'─' * 28}"
    )
    send_telegram(header)
    time.sleep(0.5)

    # ── Individual job cards ────────────────────────────────────────────────────
    for i, j in enumerate(jobs):
        work_type = get_work_type(
            f"{j.get('location','')} {j.get('desc_snippet','')}"
        )
        tags_str  = " ".join(f"`{t}`" for t in (j.get("tags") or [])[:4])
        company   = tg_escape(j.get("company") or "—")
        title     = tg_escape(j.get("title","No title"))
        source    = tg_escape(j.get("source",""))
        location  = tg_escape(j.get("location","Remote"))
        url       = j.get("url","")

        card = (
            f"*{title}*\n"
            f"🏢 {company}  •  📡 {source}\n"
            f"📍 {location}  •  {tg_escape(work_type)}\n"
        )
        if tags_str:
            card += f"{tags_str}\n"
        card += f"[Apply →]({url})"

        send_telegram(card)

        # Telegram allows ~30 messages/sec; be polite
        if (i + 1) % 20 == 0:
            time.sleep(1)
        else:
            time.sleep(0.15)

    # ── Footer ──────────────────────────────────────────────────────────────────
    footer = (
        "✅ *That's all for today\\!*\n"
        "Next update tomorrow at 8:00 AM Lisbon time 🇵🇹"
    )
    send_telegram(footer)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    seen     = load_seen()
    all_jobs = collect_all()
    new_jobs = [j for j in all_jobs if job_id(j) not in seen]
    print(f"\n  🆕 New (unseen) jobs: {len(new_jobs)}")

    if not new_jobs:
        print("  Nothing new — no notification sent.")
        return

    # Persist before sending to avoid duplicates on retry
    seen.update(job_id(j) for j in new_jobs)
    if len(seen) > 5000:
        seen = set(list(seen)[-5000:])
    save_seen(seen)

    send_summary(new_jobs)
    print(f"  📲 Sent {len(new_jobs)} job cards to Telegram.")

if __name__ == "__main__":
    main()
