#!/usr/bin/env bash
set -euo pipefail
case_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$case_dir/../common/build.sh" "$case_dir/benchmark.c" "${1:-$case_dir/../build/B01_spsc_ring}"
