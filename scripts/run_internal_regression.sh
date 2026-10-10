#!/usr/bin/env bash
set -euo pipefail
internal_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
local_clang="$internal_root/../.tools/clang18/bin/clang"
internal_args=()
if [[ -n "${PROTOTYPE_CLANG:-}" ]]; then
  internal_args+=(--clang "$PROTOTYPE_CLANG")
elif [[ -x "$local_clang" ]]; then
  internal_args+=(--clang "$local_clang")
fi
cd -- "$internal_root"
exec python3 -m prototype.internal "${internal_args[@]}" "$@"
