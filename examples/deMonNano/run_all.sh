#!/usr/bin/env bash
# Run every example of this folder from the AMAC root, then list the failures.
# Usage: bash examples/<software>/run_all.sh

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here/../.." || exit 1

failed=()
for script in "$here"/[0-9][0-9]_*.py; do
    echo "=== ${script#"$PWD"/}"
    python "$script" || failed+=("${script##*/}")
done

echo
echo "${#failed[@]} failure(s)"
[ "${#failed[@]}" -eq 0 ] || { printf '  %s\n' "${failed[@]}"; exit 1; }
