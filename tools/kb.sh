#!/usr/bin/env bash
# Shared coordination bus: the `knowledge-base` branch, checked out in a sibling worktree
# (<repo>-kb) so your feature branch is never disturbed.
#   tools/kb.sh sync                       update the worktree, print its path
#   tools/kb.sh show [area]                sync, then print all four STATUS blocks (or one full file)
#   tools/kb.sh publish <area> "message"   commit and push ONLY your team file (edit it in the worktree first)
set -euo pipefail
AREAS="model-ranking data-engineering-db ui-dashboard triage-playbook-gemini"
COMMON=$(git rev-parse --path-format=absolute --git-common-dir)
MAIN=$(cd "$COMMON/.." && pwd)
WT="${MAIN}-kb"
cmd="${1:-show}"; shift || true

ensure_wt() {
  if [ ! -e "$WT/.git" ]; then
    git -C "$MAIN" fetch -q origin knowledge-base 2>/dev/null || true
    if git -C "$MAIN" show-ref --verify --quiet refs/heads/knowledge-base; then
      git -C "$MAIN" worktree add "$WT" knowledge-base >/dev/null
    elif git -C "$MAIN" show-ref --verify --quiet refs/remotes/origin/knowledge-base; then
      git -C "$MAIN" worktree add -b knowledge-base "$WT" origin/knowledge-base >/dev/null
    else
      echo "knowledge-base branch not found locally or on origin" >&2; exit 1
    fi
  fi
  if git -C "$WT" remote get-url origin >/dev/null 2>&1; then
    if ! git -C "$WT" pull --rebase --autostash -q origin knowledge-base >/dev/null 2>&1; then
      echo "(could not pull origin/knowledge-base; showing local copy)" >&2
    fi
  fi
}

case "$cmd" in
  sync) ensure_wt; echo "$WT" ;;
  show)
    ensure_wt
    if [ -n "${1:-}" ]; then cat "$WT/docs/kb/team/$1.md"; exit 0; fi
    for a in $AREAS; do
      echo "== $a"
      sed -n '/STATUS-START/,/STATUS-END/p' "$WT/docs/kb/team/$a.md" | grep -v -e 'STATUS-START' -e 'STATUS-END'
    done
    echo; echo "Full files: $WT/docs/kb/team/   (edit only your own)" ;;
  publish)
    area="${1:?usage: kb.sh publish <area> \"message\"}"; msg="${2:?message required}"
    case " $AREAS " in *" $area "*) ;; *) echo "unknown area: $area (one of: $AREAS)" >&2; exit 1;; esac
    ensure_wt
    f="docs/kb/team/$area.md"; cd "$WT"
    other=$(git status --porcelain | grep -v " $f\$" || true)
    if [ -n "$other" ]; then echo "Other files changed in the kb worktree; revert them first:" >&2; echo "$other" >&2; exit 1; fi
    if git diff --quiet -- "$f"; then echo "nothing to publish (no change in $f)"; exit 0; fi
    sed -i.bak "s/^LAST_UPDATED:.*/LAST_UPDATED: $(date -u +%Y-%m-%dT%H:%MZ)/" "$f" && rm -f "$f.bak"
    git add "$f"; git commit -q -m "kb($area): $msg"
    if git remote get-url origin >/dev/null 2>&1; then
      if git pull --rebase -q origin knowledge-base && git push -q origin knowledge-base; then echo "published and pushed"
      else echo "committed locally; push failed. Run: git -C $WT push origin knowledge-base" >&2; fi
    else echo "committed locally (no origin remote)"; fi ;;
  *) echo "usage: tools/kb.sh sync | show [area] | publish <area> \"message\"" >&2; exit 1 ;;
esac
