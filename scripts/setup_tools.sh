#!/usr/bin/env bash
# Isolated Ubuntu 24.04/amd64 Clang setup. Does not modify system packages,
# shell startup files, or an existing opam switch.
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tools_dir=${CASE_TOOLS_DIR:-"$(dirname -- "$project_dir")/.tools"}
clang_root="$tools_dir/clang18"
clang_bin=${PROTOTYPE_CLANG:-}
herd_bin=${PROTOTYPE_HERD7:-}

resolve_tool() {
  local executable
  executable=$(command -v -- "$1") || {
    printf 'Executable not found: %s\n' "$1" >&2
    return 1
  }
  realpath -e -- "$executable"
}

if [[ -z "$clang_bin" ]]; then
  clang_bin=$(command -v clang || true)
fi
if [[ -z "$clang_bin" && -x "$clang_root/bin/clang" ]]; then
  clang_bin="$clang_root/bin/clang"
fi

if [[ -z "$clang_bin" ]]; then
  # These are the official Ubuntu Noble LLVM 18 packages. SHA256 values are
  # from Ubuntu's apt package index; they pin both version and contents.
  . /etc/os-release
  if [[ "$ID" != ubuntu || "$VERSION_ID" != 24.04 || "$(uname -m)" != x86_64 ]]; then
    printf '%s\n' 'Automatic Clang extraction requires Ubuntu 24.04 amd64.' \
      'Install Clang for this platform and rerun with PROTOTYPE_CLANG=/path/to/clang.' >&2
    exit 1
  fi
  mkdir -p "$clang_root/debs" "$clang_root/bin"
  while read -r component package sha; do
    filename="${package}_18.1.3-1ubuntu1_amd64.deb"
    archive="$clang_root/debs/$package.deb"
    if [[ ! -f "$archive" ]] || ! printf '%s  %s\n' "$sha" "$archive" | sha256sum --check --status; then
      # Use CURL_NO_PROXY='*' if an inherited proxy is unavailable.
      curl_args=(--fail --location --retry 2 --connect-timeout 20 --max-time 300)
      if [[ -n "${CURL_NO_PROXY:-}" ]]; then
        curl_args+=(--noproxy "$CURL_NO_PROXY")
      fi
      curl "${curl_args[@]}" \
        "https://archive.ubuntu.com/ubuntu/pool/$component/l/llvm-toolchain-18/$filename" \
        --output "$archive"
    fi
    printf '%s  %s\n' "$sha" "$archive" | sha256sum --check --status
    dpkg-deb -x "$archive" "$clang_root"
  done <<'PACKAGES'
universe clang-18 628b16701014ef7ad648380b20ea74b90dd543857f933b3e34d2fc042783de25
main libclang-cpp18 e91eda104813ee0468d145d010a4a4e142401f3f17f9a65596c66d416298d018
main libllvm18 af6197096ce3b89aab86de59f01c1b5feb008b2ae1514a03906c0664edb8b0b1
universe libclang-common-18-dev d41631bb752815a8196261d1030c096591c59678c8adfbf2e6a740a691b49e80
main libclang1-18 1ed67106d743ab4f12db2726c5fc11c436c5e1fba613e9f1006bf3fa05cc69bd
PACKAGES
  cat > "$clang_root/bin/clang" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
clang_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export LD_LIBRARY_PATH="$clang_root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$clang_root/usr/bin/clang-18" "$@"
WRAPPER
  chmod +x "$clang_root/bin/clang"
  clang_bin="$clang_root/bin/clang"
fi

if [[ -z "$herd_bin" ]]; then
  herd_bin=$(command -v herd7 || true)
fi
if [[ -z "$herd_bin" ]]; then
  for candidate in "$HOME"/.opam/*/bin/herd7; do
    if [[ -x "$candidate" ]]; then
      herd_bin="$candidate"
      break
    fi
  done
fi

clang_bin=$(resolve_tool "$clang_bin")
"$clang_bin" --version
if [[ -z "$herd_bin" ]]; then
  printf '%s\n' 'Clang is ready, but herd7 is missing.' \
    'Install herdtools7 in your chosen opam switch and rerun with PROTOTYPE_HERD7=/path/to/herd7.' >&2
  exit 1
fi
herd_bin=$(resolve_tool "$herd_bin")
"$herd_bin" -version
herd_prefix=$(dirname -- "$(dirname -- "$(readlink -f -- "$herd_bin")")")
model_dir="$herd_prefix/share/herdtools7/herd"
for model in x86tso.cat riscv.cat; do
  if [[ ! -f "$model_dir/$model" ]]; then
    printf 'Missing model: %s\n' "$model_dir/$model" >&2
    exit 1
  fi
done

mkdir -p "$tools_dir"
env_file="$tools_dir/case-regression-env.sh"
{
  printf 'export PROTOTYPE_CLANG=%q\n' "$clang_bin"
  printf 'export PROTOTYPE_HERD7=%q\n' "$herd_bin"
  printf 'export PROTOTYPE_X86_MODEL=%q\n' "$model_dir/x86tso.cat"
  printf 'export PROTOTYPE_RISCV_MODEL=%q\n' "$model_dir/riscv.cat"
  printf 'export PATH=%q:%q:"$PATH"\n' "$(dirname -- "$clang_bin")" "$(dirname -- "$herd_bin")"
} > "$env_file"
printf '\nLoad the discovered tool paths:\n  source %q\n' "$env_file"
