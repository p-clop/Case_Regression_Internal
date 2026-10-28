#!/usr/bin/env bash
set -euo pipefail
source_file=$1
output_file=$2
mkdir -p -- "$(dirname -- "$output_file")"
compiler=${CC:-cc}
optimization=${BENCH_OPT:--O2}
case "$optimization" in -O0|-O1|-O2|-O3) ;; *) echo 'BENCH_OPT must be -O0/-O1/-O2/-O3' >&2; exit 2;; esac
extra=()
if [[ ${BENCH_INJECT_CORRUPTION:-0} == 1 ]]; then extra+=(-DBENCH_INJECT_CORRUPTION=1); fi
"$compiler" -std=c11 "$optimization" -g -Wall -Wextra -Werror -pthread \
    "${extra[@]}" "$source_file" -o "$output_file"
