#!/usr/bin/env bash
set -euo pipefail

# ORI-C cleanup: remove the generic maintainer workflows added by mistake.
# Run this script from the repository root.

if [ ! -d ".github/workflows" ]; then
  echo "ERROR: .github/workflows not found. Run from the repository root." >&2
  exit 1
fi

remove_file() {
  local path="$1"
  if [ -f "$path" ]; then
    rm -f "$path"
    echo "removed: $path"
  else
    echo "skip:    $path"
  fi
}

# Unrelated generic workflows that clutter the Actions tab.
remove_file ".github/workflows/codeql.yml"
remove_file ".github/workflows/dependency-review.yml"
remove_file ".github/workflows/secrets.yml"
remove_file ".github/workflows/docs.yml"
remove_file ".github/workflows/release.yml"
remove_file ".github/workflows/coverage.yml"
remove_file ".github/workflows/package.yml"

# Related config/docs introduced with the same patch.
remove_file ".github/dependency-review-config.yml"
remove_file "docs/MAINTAINERS_WORKFLOWS.md"
remove_file "docs/PYTHON_SUPPORT.md"

# Keep the original ORI-C workflows only. This check does not delete anything,
# it prints what remains so the Actions tab can be verified before commit.
echo ""
echo "Remaining workflows:"
find .github/workflows -maxdepth 1 -type f -name '*.yml' -o -name '*.yaml' | sort

echo ""
echo "Now run:"
echo "  git status"
echo "  git add -A .github docs"
echo "  git commit -m \"cleanup: remove unrelated maintainer workflows\""
echo "  git push"
