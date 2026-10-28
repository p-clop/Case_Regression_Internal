#!/usr/bin/env bash
set -euo pipefail
case_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$case_root"
case_args=()
if [[ -n "${PROTOTYPE_CLANG:-}" ]]; then
  case_args+=(--clang "$PROTOTYPE_CLANG")
elif [[ -x "$case_root/../.tools/clang18/bin/clang" ]]; then
  case_args+=(--clang "$case_root/../.tools/clang18/bin/clang")
fi
exec python3 -m prototype.architecture "${case_args[@]}" "$@"
