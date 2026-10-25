#!/usr/bin/env bash
# Resolve session kind and namespaced slug from a lecture/practice directory path.
# Usage: source session-slug.sh && session_slug "$SESSION_DIR"
# Sets: SESSION_KIND (lectures|practices|assignments), SESSION_SLUG (e.g. lectures/01-intro)

session_slug() {
  local dir="$1"
  local parent base

  dir="$(cd "$dir" && pwd)"
  parent="$(basename "$(dirname "$dir")")"
  base="$(basename "$dir")"

  case "$parent" in
    lectures|practices|assignments)
      SESSION_KIND="$parent"
      SESSION_SLUG="${parent}/${base}"
      ;;
    *)
      echo "Error: session directory must be under lectures/, practices/, or assignments/: ${dir}" >&2
      return 1
      ;;
  esac
}
