#!/usr/bin/env python3
"""Turn `git log <last-tag>..HEAD` into a release-notes web page, and publish
it to a public deed.page URL only after you type y.

  python3 release_notes_page.py            # build notes.html, ask before publishing
  python3 release_notes_page.py --delete   # take the page down again
"""
import html, json, os, pathlib, secrets, subprocess, sys, urllib.request

CONF = pathlib.Path.home() / ".config" / "deed-page"
API = "https://deed.page/v1/sites"
GROUPS = [("feat", "New"), ("fix", "Fixed"), ("perf", "Faster"), ("docs", "Docs")]

def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()

def build():
    since = git("describe", "--tags", "--abbrev=0")
    rng = f"{since}..HEAD" if since else "HEAD"
    lines = git("log", rng, "--no-merges", "--pretty=%h\x1f%s").splitlines()
    buckets = {label: [] for _, label in GROUPS}; buckets["Other"] = []
    for line in lines:
        sha, subj = line.split("\x1f", 1)
        kind = subj.split(":", 1)[0].split("(", 1)[0].lower()
        label = dict(GROUPS).get(kind, "Other")
        text = subj.split(":", 1)[1].strip() if label != "Other" and ":" in subj else subj
        buckets[label].append(f"<li>{html.escape(text)} <code>{sha}</code></li>")
    repo = html.escape(pathlib.Path(git("rev-parse", "--show-toplevel")).name)
    title = f"{repo}: changes since {html.escape(since) if since else 'the first commit'}"
    body = "".join(f"<h2>{k}</h2><ul>{''.join(v)}</ul>" for k, v in buckets.items() if v)
    page = (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            f"<title>{title}</title><style>body{{font:16px/1.5 system-ui;max-width:42rem;margin:2rem auto;padding:0 1rem}}"
            f"code{{color:#666}}</style><h1>{title}</h1><p>{len(lines)} commits</p>{body}")
    pathlib.Path("notes.html").write_text(page)
    return len(lines), title

def request(method, url, data=None):
    req = urllib.request.Request(url, data=data, method=method)
    tok = os.environ.get("DEEDPAGE_TOKEN", "")
    if not tok and (CONF / "token").exists():
        tok = (CONF / "token").read_text().strip()
    if tok: req.add_header("Authorization", f"Bearer {tok}")
    if data: req.add_header("Content-Type", "text/html")
    with urllib.request.urlopen(req) as r:
        return r.status, r.read().decode() or "{}"

def main():
    slug_file = CONF / "release-notes-slug"
    if "--delete" in sys.argv:
        slug = slug_file.read_text().strip()
        print(request("DELETE", f"{API}/{slug}")[0], "deleted", slug); return
    n, title = build()
    print(f"Wrote notes.html: {title} ({n} commits). Open it and check it first.")
    if input("Publish notes.html to a public URL? Anyone with the link can read it. [y/N] ").strip() != "y":
        print("Not published."); return
    slug = slug_file.read_text().strip() if slug_file.exists() else f"notes-{secrets.token_hex(4)}"
    status, raw = request("PUT", f"{API}?slug={slug}", pathlib.Path("notes.html").read_bytes())
    resp = json.loads(raw)
    CONF.mkdir(parents=True, exist_ok=True); os.chmod(CONF, 0o700)
    slug_file.write_text(slug)
    if resp.get("token"):  # first anonymous publish returns an owner token: keep it, never print it
        (CONF / "token").write_text(resp["token"]); os.chmod(CONF / "token", 0o600)
    print(status, resp.get("url", f"https://{slug}.deed.page/"))

if __name__ == "__main__":
    main()
