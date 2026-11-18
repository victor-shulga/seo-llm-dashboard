"""DataForSEO transport for the AI-visibility report: curl subprocesses, not urllib.

urllib inside threads hangs whole runs on macOS (resolver, Errno 8), so every request
goes through curl, which is safe to fan out across threads.

Credentials, first hit wins (never printed or written anywhere):
  1. env DATAFORSEO_API_KEY                     Basic-auth token = base64("login:password")
  2. env DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD  your DataForSEO API login and API password
  3. env DATAFORSEO_ENV -> path to a .env file holding either of the above
  4. ~/.config/dataforseo/key                   a bare Basic-auth token (chmod 600)
"""
import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

BASE = "https://api.dataforseo.com/v3"


def _token(login, password):
    return base64.b64encode(f"{login}:{password}".encode()).decode()


def _from_env_map(env):
    if env.get("DATAFORSEO_API_KEY"):
        return env["DATAFORSEO_API_KEY"].strip()
    if env.get("DATAFORSEO_LOGIN") and env.get("DATAFORSEO_PASSWORD"):
        return _token(env["DATAFORSEO_LOGIN"].strip(), env["DATAFORSEO_PASSWORD"].strip())
    return None


def _read_env_file(path):
    out = {}
    for line in Path(path).expanduser().read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:]
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _key():
    key = _from_env_map(os.environ)
    if key:
        return key
    env_file = os.environ.get("DATAFORSEO_ENV")
    if env_file and Path(env_file).expanduser().exists():
        key = _from_env_map(_read_env_file(env_file))
        if key:
            return key
    bare = Path.home() / ".config/dataforseo/key"
    if bare.exists():
        return bare.read_text().strip()
    raise SystemExit("No DataForSEO credentials: set DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD "
                     "(or DATAFORSEO_API_KEY), point DATAFORSEO_ENV at a .env file with them, "
                     "or put the Basic-auth token in ~/.config/dataforseo/key (chmod 600).")


_KEY = None   # resolved on the first API call, so local steps (review, finalize) need no key


def call(method, path, body=None, tries=3):
    global _KEY
    if _KEY is None:
        _KEY = _key()
    cmd = ["curl", "-sS", "--max-time", "400", "-X", method, BASE + path,
           "-H", f"Authorization: Basic {_KEY}", "-H", "Content-Type: application/json"]
    if body is not None:
        cmd += ["--data", json.dumps([body])]
    last = None
    for attempt in range(tries):
        p = subprocess.run(cmd, capture_output=True, text=True)
        try:
            r = json.loads(p.stdout)
        except ValueError:
            last = {"error": (p.stderr or p.stdout)[:200]}
            time.sleep(3 * (attempt + 1))
            continue
        if r.get("status_code") in (40100, 40101, 40104):
            raise SystemExit("DataForSEO rejected the key (401). Re-check the credentials.")
        task = (r.get("tasks") or [{}])[0]
        if task.get("status_code") == 20000:
            return r
        last = {"error": task.get("status_message") or r.get("status_message")}
        time.sleep(3 * (attempt + 1))
    return {"failed": True, **(last or {})}


def resolve(url):
    """Gemini returns vertexaisearch grounding redirects; follow them to the real page."""
    if "grounding-api-redirect" not in url and "vertexaisearch" not in url:
        return url
    p = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{redirect_url}",
                        "--max-time", "15", url], capture_output=True, text=True)
    return p.stdout.strip() or url


TWO_LEVEL = ("com.ua", "org.ua", "net.ua", "biz.ua", "in.ua", "kiev.ua", "kyiv.ua", "lviv.ua",
             "edu.ua", "gov.ua", "co.uk", "org.uk", "com.au", "co.il", "com.pl")


def domain(url):
    """Registrable domain: uk.example.com and www.example.com are one site."""
    host = urlparse(url).netloc.lower().split(":")[0]
    parts = host.split(".")
    keep = 3 if any(host.endswith("." + t) for t in TWO_LEVEL) else 2
    return ".".join(parts[-keep:]) if len(parts) > keep else host


def visible(text):
    """What a reader sees: markdown link targets and bare URLs removed.

    Without this a name inside a URL counts as a mention (seen in a real run: a
    competitor's name inside the slug of a link to an unrelated firm was credited
    to that competitor)."""
    return re.sub(r"https?://\S+", " ", re.sub(r"\]\([^)]*\)", "]", text))


def live_answer(llm, model, prompt, country="US", max_tokens=4096):
    """Final answer text (reasoning dropped) + resolved source URLs for one prompt/model."""
    body = {"user_prompt": prompt, "model_name": model, "web_search": True,
            "max_output_tokens": max_tokens}
    if llm != "gemini" and country:
        body["web_search_country_iso_code"] = country
    r = call("POST", f"/ai_optimization/{llm}/llm_responses/live", body)
    if r.get("failed"):
        return {"status": "not_measured", "error": r.get("error")}
    res = (r["tasks"][0].get("result") or [{}])[0]
    text, urls = [], []
    for it in res.get("items") or []:
        if it.get("type") != "message":
            continue                      # reasoning blocks are not what the user sees
        for sec in it.get("sections") or []:
            if sec.get("type", "text") == "text":
                text.append(sec.get("text") or "")
            for a in sec.get("annotations") or []:
                if a.get("url"):
                    urls.append(a["url"])
        for a in it.get("annotations") or []:
            if a.get("url"):
                urls.append(a["url"])
    body_text = "\n".join(text)
    urls += re.findall(r"\]\((https?://[^)\s]+)\)", body_text)   # inline-only sources
    seen, sources = set(), []
    for u in urls:
        u = resolve(u)
        if u not in seen:
            seen.add(u)
            sources.append(u)
    return {"status": "measured", "text": body_text, "sources": sources,
            "web_search": res.get("web_search"), "cost": r.get("cost") or 0}
