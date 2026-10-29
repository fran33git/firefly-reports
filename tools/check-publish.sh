#!/usr/bin/env bash
#
# check-publish.sh — nothing private goes into the public history.
#
#   tools/check-publish.sh BASE..HEAD   the commits of a range (CI)
#   tools/check-publish.sh              what a push is about to publish (pre-push hook; falls back
#                                       to origin/main..HEAD for a new branch or a rewritten remote)
#
# Every commit of the range is inspected, not only the final tree: a file added and removed again
# is still public. Merge commits are compared with their first parent, renames count as additions.
#   1. Paths that never belong in the repository (FORBIDDEN_PATHS below).
#   2. Personal strings, read from a pattern list that is NOT in the repository: one extended
#      regex per line, matched case-insensitively (write it in lowercase), '#' starts a comment.
#      It is matched against added lines, paths, author and committer identities and messages.
#        CI:    $PUBLISH_DENY_PATTERNS, a repository secret
#        local: $PUBLISH_DENY_FILE, default ~/.config/firefly-reports/deny-patterns
#
# Findings name the commit and the file, never the text that matched: CI logs are public.
# Any failure of the scan itself (bad range, invalid pattern) is a failure of the check.
# Without a pattern list only check 1 runs, unless PUBLISH_REQUIRE_PATTERNS=true (the repository
# owner's own pull requests and pushes in CI), which turns a missing list into a failure.

set -euo pipefail

FORBIDDEN_PATHS='(^|/)(\.mailmap|\.mcp\.json|\.env|firefly-reports\.toml|beancount_map\.yaml)$|(^|/)(\.remember|\.claude|\.superpowers|\.dev-notes|\.idea|\.vscode)(/|$)|(^|/)KIMI[^/]*$|\.(bundle|bak|orig|pem|pfx)$'

if [[ $# -ge 1 ]]; then
  range=$1
else
  from=${PRE_COMMIT_FROM_REF:-}
  to=${PRE_COMMIT_TO_REF:-HEAD}
  if [[ -z $from || $from =~ ^0+$ ]] || ! git cat-file -e "$from^{commit}" 2>/dev/null; then
    from=$(git merge-base origin/main "$to" 2>/dev/null || true)
  fi
  if [[ -z $from ]]; then
    echo "publish: no base to compare with; run 'git fetch origin' or pass BASE..HEAD" >&2
    exit 1
  fi
  range="$from..$to"
fi

# Plain git options for every log below: unquoted paths, renames as add + delete, merges against
# their first parent.
GIT_LOG=(git -c core.quotePath=false log --no-color --no-renames --diff-merges=first-parent)

status=0
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
patterns=$work/patterns

# 1. Paths. Each stage is its own command, so that a failing git (bad range) stops the script.
"${GIT_LOG[@]}" -z --name-only --diff-filter=AM --format= "$range" >"$work/paths"
while IFS= read -r -d '' path; do
  echo "publish: forbidden path in the history: $path" >&2
  status=1
done < <(sort -zu "$work/paths" | { grep -zE "$FORBIDDEN_PATHS" || [[ $? -eq 1 ]]; })

# 2. Personal strings
: >"$patterns"
if [[ -n ${PUBLISH_DENY_PATTERNS:-} ]]; then
  printf '%s\n' "$PUBLISH_DENY_PATTERNS" >"$patterns"
elif [[ -f ${PUBLISH_DENY_FILE:-$HOME/.config/firefly-reports/deny-patterns} ]]; then
  cat "${PUBLISH_DENY_FILE:-$HOME/.config/firefly-reports/deny-patterns}" >"$patterns"
fi
# Comments and blank lines out: an empty regex would match everything.
sed -i -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' "$patterns"

if [[ -s $patterns ]]; then
  # A list that does not compile is a failure, reported without quoting it.
  rc=0
  grep -Eq -f "$patterns" /dev/null 2>/dev/null || rc=$?
  if [[ $rc -gt 1 ]]; then
    echo "publish: the pattern list contains an invalid regular expression" >&2
    exit 1
  fi

  # awk reads the list itself (its stderr is dropped: its messages can quote a pattern).
  scan() { # name awk-program
    awk -v pat="$patterns" "BEGIN { while ((getline p < pat) > 0) re[n++] = tolower(p) }
      function hit(text,   i, t) {
        t = tolower(text)
        for (i = 0; i < n; i++) if (t ~ re[i]) return 1
        return 0
      }
      function report(what) {
        key = commit SUBSEP what
        if (!(key in seen)) { seen[key] = 1; print \"personal string in \" what \" of commit \" commit }
      }
      $2" 2>/dev/null
  }

  # 2a. Identities and messages, one NUL-terminated record per commit (no in-band delimiters).
  # shellcheck disable=SC2016
  "${GIT_LOG[@]}" -z --format='%h%n%an <%ae>%n%cn <%ce>%n%B' "$range" | tr '\0' '\001' |
    scan meta 'BEGIN { RS = "\001" }
      { commit = $0; sub(/\n.*/, "", commit); body = $0; sub(/^[^\n]*\n/, "", body)
        if (hit(body)) report("the identity or message") }' >"$work/meta" || {
    echo "publish: the scan of identities and messages failed" >&2
    exit 1
  }

  # 2b. Added lines and file names. The only "@@@ " lines are the ones --format prints: diff
  # lines always start with ' ', '+' or '-'.
  # shellcheck disable=SC2016
  "${GIT_LOG[@]}" -p -U0 --format='@@@ %h' "$range" |
    scan diff '/^@@@ / { commit = $2; file = ""; next }
      /^\+\+\+ "?b\// { file = $0; sub(/^\+\+\+ "?b\//, "", file); sub(/"?\t?$/, "", file)
                        if (hit(file)) report("a path name"); next }
      /^\+\+\+ / { file = ""; next }
      /^\+/ { if (hit(substr($0, 2))) report("file " (file != "" ? file : "(unnamed)")) }' \
    >"$work/diff" || {
    echo "publish: the scan of the added lines failed" >&2
    exit 1
  }

  if [[ -s $work/meta || -s $work/diff ]]; then
    sed 's/^/publish: /' "$work/meta" "$work/diff" >&2
    status=1
  fi
elif [[ ${PUBLISH_REQUIRE_PATTERNS:-false} == true ]]; then
  echo "publish: no pattern list (secret PUBLISH_DENY_PATTERNS is missing or empty)" >&2
  status=1
else
  echo "publish: no pattern list, personal strings not checked (see tools/check-publish.sh)" >&2
fi

if [[ $status -ne 0 ]]; then
  cat >&2 <<'MSG'

Not safe to publish. Fix the new commits, or rewrite the unpublished ones
(git rebase -i / git commit --amend) before pushing.
MSG
fi
exit $status
