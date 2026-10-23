#!/usr/bin/env bash
#
# check-identity.sh — commits are authored as the GitHub account, with its noreply address.
#
#   tools/check-identity.sh              the identity the next commit would use
#   tools/check-identity.sh BASE..HEAD   every commit of a range (CI)
#
# Accepted: author fran33git or a bot ("name[bot]"); committer also GitHub's web-flow
# (merges done on github.com). The email must be a users.noreply.github.com address, so
# a personal address never ends up in the public history. Trailers are not checked.

set -euo pipefail

NAME_RE='^(fran33git|[A-Za-z0-9._-]+\[bot\])$'
EMAIL_RE='@users\.noreply\.github\.com$'
status=0

check() { # role name email where
  local role=$1 name=$2 email=$3 where=$4
  if [[ $role == committer && $name == GitHub && $email == noreply@github.com ]]; then
    return
  fi
  if ! [[ $name =~ $NAME_RE ]]; then
    echo "identity: $where: $role name '$name' is not fran33git" >&2
    status=1
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
  git config user.name fran33git
  git config user.email 80598630+fran33git@users.noreply.github.com
Already-made commits: git rebase -r <base> --exec 'git commit --amend --no-edit --reset-author'
MSG
fi
exit $status
