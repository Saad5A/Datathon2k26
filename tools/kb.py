#!/usr/bin/env python3
"""Cross-platform helper for the shared `knowledge-base` branch (Windows, Mac, Linux).
The branch is checked out in a sibling worktree "<repo>-kb" so your feature branch is never disturbed.
  python tools/kb.py sync                       update the worktree, print its path
  python tools/kb.py show [area]                sync, then print all four STATUS blocks (or one full file)
  python tools/kb.py publish <area> "message"   commit and push ONLY your team file (edit it in the worktree first)
Areas: model-ranking, data-engineering-db, ui-dashboard, triage-playbook-gemini"""
import datetime, os, re, subprocess, sys

AREAS = ["model-ranking", "data-engineering-db", "ui-dashboard", "triage-playbook-gemini"]

def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r

def paths():
    common = git("rev-parse", "--git-common-dir").stdout.strip()
    common = os.path.abspath(common)
    main = os.path.dirname(common)
    return main, main + "-kb"

def remote_has_branch(cwd):
    return git("ls-remote", "--exit-code", "--heads", "origin", "knowledge-base", cwd=cwd, check=False).returncode == 0

def has_origin(cwd):
    return git("remote", "get-url", "origin", cwd=cwd, check=False).returncode == 0

def ensure_wt():
    main, wt = paths()
    if not os.path.exists(os.path.join(wt, ".git")):
        git("fetch", "-q", "origin", "knowledge-base", cwd=main, check=False)
        if git("show-ref", "--verify", "--quiet", "refs/heads/knowledge-base", cwd=main, check=False).returncode == 0:
            git("worktree", "add", wt, "knowledge-base", cwd=main)
        elif git("show-ref", "--verify", "--quiet", "refs/remotes/origin/knowledge-base", cwd=main, check=False).returncode == 0:
            git("worktree", "add", "-b", "knowledge-base", wt, "origin/knowledge-base", cwd=main)
        else:
            sys.exit("knowledge-base branch not found locally or on origin. Run: git fetch origin")
    if has_origin(wt):
        if remote_has_branch(wt):
            r = git("pull", "--rebase", "--autostash", "-q", "origin", "knowledge-base", cwd=wt, check=False)
            if r.returncode != 0:
                print("(pull failed; showing local copy)", file=sys.stderr)
        else:
            print("(knowledge-base not on origin yet; push it once: git push -u origin knowledge-base)", file=sys.stderr)
    return wt

def main_cli():
    args = sys.argv[1:]
    cmd = args[0] if args else "show"
    rest = args[1:]
    if cmd == "sync":
        print(ensure_wt())
    elif cmd == "show":
        wt = ensure_wt()
        if rest:
            print(open(os.path.join(wt, "docs", "kb", "team", rest[0] + ".md"), encoding="utf-8").read()); return
        for a in AREAS:
            txt = open(os.path.join(wt, "docs", "kb", "team", a + ".md"), encoding="utf-8").read()
            m = re.search(r"<!-- STATUS-START -->\n(.*?)<!-- STATUS-END -->", txt, re.S)
            print(f"== {a}\n{m.group(1).strip() if m else '(no STATUS block)'}")
        print(f"\nFull files: {os.path.join(wt, 'docs', 'kb', 'team')}   (edit only your own)")
    elif cmd == "publish":
        if len(rest) < 2: sys.exit('usage: python tools/kb.py publish <area> "message"')
        area, msg = rest[0], rest[1]
        if area not in AREAS: sys.exit(f"unknown area: {area} (one of: {', '.join(AREAS)})")
        wt = ensure_wt()
        f = f"docs/kb/team/{area}.md"
        changed = [l[3:].strip().strip('"') for l in git("status", "--porcelain", cwd=wt).stdout.splitlines() if l.strip()]
        other = [c for c in changed if c.replace("\\", "/") != f]
        if other: sys.exit("Other files changed in the kb worktree; revert them first:\n" + "\n".join(other))
        if git("diff", "--quiet", "--", f, cwd=wt, check=False).returncode == 0:
            print(f"nothing to publish (no change in {f})"); return
        p = os.path.join(wt, f)
        txt = open(p, encoding="utf-8").read()
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        txt = re.sub(r"^LAST_UPDATED:.*$", f"LAST_UPDATED: {stamp}", txt, count=1, flags=re.M)
        open(p, "w", encoding="utf-8", newline="").write(txt)
        git("add", f, cwd=wt)
        git("commit", "-q", "-m", f"kb({area}): {msg}", cwd=wt)
        if has_origin(wt):
            if remote_has_branch(wt):
                git("pull", "--rebase", "-q", "origin", "knowledge-base", cwd=wt, check=False)
            r = git("push", "-q", "-u", "origin", "knowledge-base", cwd=wt, check=False)
            print("published and pushed" if r.returncode == 0 else f"committed locally; push failed ({r.stderr.strip()}). Run: git -C \"{wt}\" push -u origin knowledge-base")
        else:
            print("committed locally (no origin remote)")
    else:
        sys.exit(__doc__)

if __name__ == "__main__":
    try: main_cli()
    except RuntimeError as e: sys.exit(str(e))
