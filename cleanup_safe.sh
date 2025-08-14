#!/usr/bin/env bash
# Interactive project cleanup: finds common junk and asks before deleting.
# Use --all-yes to skip prompts; --list to only list.

set -euo pipefail

ALL_YES="no"
ROOT=""
MODE="ask"  # ask | list
PROTECT=()

usage() {
  cat <<'USAGE'
Usage: cleanup_safe.sh [--all-yes] [--list] [--root <path>] [--protect <path> ...]

Options:
  --all-yes        Delete without prompting (NON-INTERACTIVE).
  --list           Only list candidates (no deletion).
  --root <path>    Project root (default: current directory).
  --protect <p>    Additional paths to protect from deletion (repeatable).

Notes:
- Targets common junk: caches, bytecode, Apple junk, build artifacts, logs, archives, etc.
- Never touches: .git, .github, .vscode, .gitignore, .gitattributes, .editorconfig, .env, .python-version, vinv
USAGE
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all-yes) ALL_YES="yes"; shift ;;
    --list) MODE="list"; shift ;;
    --root) ROOT="${2-}"; shift 2 ;;
    --protect) PROTECT+=("$2"); shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "${ROOT}" ]]; then ROOT="$(pwd)"; fi
cd "$ROOT"

echo "Project root: $(pwd)"
echo "Mode       : $MODE"
echo "All-yes    : $ALL_YES"
echo

# Built-in protected paths
PROTECT+=( ".git" ".github" ".vscode" ".gitignore" ".gitattributes" ".editorconfig" ".env" ".python-version" "vinv" )

# Helper: check if a path is protected
is_protected() {
  local p="$1"
  for prot in "${PROTECT[@]}"; do
    if [[ "$p" == "$prot" || "$p" == ./"$prot" || "$p" == */"$prot" || "$p" == ./*/"$prot" ]]; then
      return 0
    fi
  done
  return 1
}

delete_path() {
  local p="$1"
  if [[ -d "$p" ]]; then rm -rf -- "$p"; else rm -f -- "$p"; fi
}

confirm_and_delete() {
  local p="$1"
  if is_protected "$p"; then
    echo "SKIP (protected): ${p#./}"
    return
  fi

  local pdisp="${p#./}"

  if [[ "$MODE" == "list" && "$ALL_YES" != "yes" ]]; then
    echo "LIST: $pdisp"
    return
  fi

  if [[ "$ALL_YES" == "yes" ]]; then
    echo "DEL : $pdisp"
    delete_path "$p"
    return
  fi

  read -rp "Delete '$pdisp'? [y/N] " ans
  case "$ans" in
    y|Y|yes|YES) delete_path "$p"; echo "Deleted: $pdisp" ;;
    *)           echo "Skip: $pdisp" ;;
  esac
}

# Emit candidates (NUL-delimited) and handle them one by one
echo "Scanning for deletion candidates..."
found=0
while IFS= read -r -d '' p; do
  found=1
  confirm_and_delete "$p"
done < <(
  # Hidden junk directories (safe)
  find . -type d \( -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name ".cache" -o -name ".ipynb_checkpoints" -o -name ".idea" \) -print0
  # Virtual envs (ask)
  find . -type d \( -name "venv" -o -name ".venv" -o -name "env" \) -print0
  # Python bytecode and caches
  find . -type d -name "__pycache__" -print0
  find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -print0
  # Apple junk
  find . -type f \( -name ".DS_Store" -o -name "._*" -o -name ".AppleDouble" -o -name ".Spotlight-V100" -o -name ".Trashes" -o -name ".fseventsd" \) -print0
  # Build artifacts
  find . -type d \( -name "dist" -o -name "build" -o -name "*.egg-info" \) -print0
  # Node modules (if present)
  find . -type d -name "node_modules" -print0
  # Logs & archives
  find . -type f \( -name "*.log" -o -name "*.zip" -o -name "*.tar" -o -name "*.gz" -o -name "*.bz2" -o -name "*.7z" \) -print0
)

if [[ "$found" -eq 0 ]]; then
  echo "No deletion candidates found."
fi

echo "Done."