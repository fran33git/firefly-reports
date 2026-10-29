#!/usr/bin/env bash
#
# check-identity.sh — commits carry a GitHub noreply address, never a personal one.
#
#   tools/check-identity.sh              the identity the next commit would use
#   tools/check-identity.sh BASE..HEAD   every commit of a range (CI)
#
# Author and committer emails must be users.noreply.github.com addresses (GitHub's own
# committer for merges made on github.com is accepted too), so that a personal address
# never ends up in the public history. Names are not checked. Trailers are not checked.

set -euo pipefail

EMAIL_RE='@users\.noreply\.github\.com$'
status=0

check() { # role name email where
  local role=$1 name=$2 email=$3 where=$4
  if [[ $role == committer && $name == GitHub && $email == noreply@github.com ]]; then
    return
  fi
  if ! [[ $email =~ $EMAIL_RE ]]; then
    echo "identity: $where: $role email '$email' is not a GitHub noreply address" >&2
    status=1
  fi
}

if [[ $# -eq 0 ]]; then
  for role in author committer; do
    ident=$(git var "GIT_${role^^}_IDENT")
    name=${ident%% <*}
    email=${ident#*<}
    email=${email%%>*}
    check "$role" "$name" "$email" "next commit"
  done
else
  while IFS=$'\t' read -r sha an ae cn ce; do
    check author "$an" "$ae" "${sha:0:8}"
    check committer "$cn" "$ce" "${sha:0:8}"
  done < <(git log --format='%H%x09%an%x09%ae%x09%cn%x09%ce' "$1")
fi

if [[ $status -ne 0 ]]; then
  cat >&2 <<'MSG'

Fix for new commits (this repository only):
  git config user.email <id>+<username>@users.noreply.github.com   # GitHub > Settings > Emails
Already-made commits: git rebase -r <base> --exec 'git commit --amend --no-edit --reset-author'
MSG
fi
exit $status
