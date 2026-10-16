#!/bin/sh
# Throwaway attribution helper for the ci-watch slice.
#
# This script carries the corrected ci-watch attribution decision while it is
# developed and unit-tested. Once validated, the logic is baked inline into the
# shipped `make ci-watch` target and this file is deleted. It exists only to keep
# the Makefile self-contained at runtime.
#
# Subcommands:
#   subset-verdict <new-failures> <old-failures>
#       Prints "pre-existing" when every newly failing job also failed on the
#       base (an empty new set is a subset), otherwise "regression".
#   classify-conclusion <conclusion>
#       Prints "pass" for success, "attribute" for failure, and "block" for any
#       other value (fail-safe).
#   resolve-base <tip-sha> <workflow>
#       Walks the ancestors of <tip-sha> from the newest and prints the first
#       SHA that carries a run for <workflow>, or nothing when none does.
#
# POSIX sh only: the Make recipe runs under sh (dash on Linux), so no bashisms.

set -eu

MAX_BASE_DEPTH=50

usage() {
  echo "usage: attribution.sh <subset-verdict|classify-conclusion|resolve-base> ..." >&2
  exit 2
}

subset_verdict() {
  awk -v new="$1" -v old="$2" '
    BEGIN {
      n = split(new, na, ",")
      m = split(old, oa, ",")
      for (i = 1; i <= n; i++) {
        if (na[i] == "") continue
        found = 0
        for (j = 1; j <= m; j++) {
          if (oa[j] == na[i]) { found = 1; break }
        }
        if (!found) { print "regression"; exit }
      }
      print "pre-existing"
    }
  ' </dev/null
}

classify_conclusion() {
  case "$1" in
    success) printf 'pass\n' ;;
    failure) printf 'attribute\n' ;;
    *) printf 'block\n' ;;
  esac
}

resolve_base() {
  tip="$1"
  workflow="$2"
  current="$tip"
  depth=0
  while [ "$depth" -lt "$MAX_BASE_DEPTH" ]; do
    current=$(git rev-parse "$current~1" 2>/dev/null) || return 0
    if [ -z "$current" ]; then
      return 0
    fi
    run_id=$(gh run list --commit "$current" --workflow "$workflow" \
      --json databaseId --jq '.[0].databaseId')
    if [ -n "$run_id" ]; then
      printf '%s\n' "$current"
      return 0
    fi
    depth=$((depth + 1))
  done
  return 0
}

cmd="${1:-}"
case "$cmd" in
  subset-verdict)
    [ "$#" -ge 3 ] || usage
    subset_verdict "$2" "$3"
    ;;
  classify-conclusion)
    [ "$#" -ge 2 ] || usage
    classify_conclusion "$2"
    ;;
  resolve-base)
    [ "$#" -ge 3 ] || usage
    resolve_base "$2" "$3"
    ;;
  *)
    usage
    ;;
esac