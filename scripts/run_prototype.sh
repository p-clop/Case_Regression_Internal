#!/usr/bin/env bash
set -euo pipefail
prototype_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
local_clang="$prototype_root/../.tools/clang18/bin/clang"
prototype_args=()
if [[ -n "${PROTOTYPE_CLANG:-}" ]]; then
  prototype_args+=(--clang "$PROTOTYPE_CLANG")
elif [[ -x "$local_clang" ]]; then
  prototype_args+=(--clang "$local_clang")
fi
if [[ -n "${PROTOTYPE_HERD7:-}" ]]; then
  prototype_args+=(--herd7 "$PROTOTYPE_HERD7")
fi
if [[ -n "${PROTOTYPE_X86_MODEL:-}" ]]; then
  prototype_args+=(--x86-model "$PROTOTYPE_X86_MODEL")
fi
if [[ -n "${PROTOTYPE_RISCV_MODEL:-}" ]]; then
  prototype_args+=(--riscv-model "$PROTOTYPE_RISCV_MODEL")
fi
cd -- "$prototype_root"
exec python3 -m prototype "${prototype_args[@]}" "$@"
