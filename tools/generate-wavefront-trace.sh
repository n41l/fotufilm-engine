#!/bin/bash
# Build only the opt-in research producer/consumer trace kernels. No performance binaries.
set -euo pipefail
cd "$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().parents[1])' "$0")"
export FOTUFILM_AOT_WAVEFRONT=1 FOTUFILM_AOT_WAVEFRONT_TRACE=1
OUTPUT="$(python3 tools/aot-release.py output macos "${1:-build/wavefront-explicit-kernels}")"
HALIDE_PREFIX="$(tools/resolve-halide-toolchain.sh)"
HALIDE_PREFIX="$(cd "$HALIDE_PREFIX" && pwd -P)"
mkdir -p "$OUTPUT"
rm -f "$OUTPUT/source-key.txt"
PENDING="$(mktemp -d "$OUTPUT/.pending.XXXXXX")"
trap 'rm -rf "$PENDING"' EXIT
xcrun clang++ -std=c++17 -O2 -I"$HALIDE_PREFIX/include" -ISources/FotufilmHalide/include \
  tools/generate_halide_ios.cpp -L"$HALIDE_PREFIX/lib" -lHalide \
  -Wl,-rpath,"$HALIDE_PREFIX/lib" -o "$PENDING/generate-halide-aot"
python3 tools/aot-release.py key macos > "$PENDING/source-key.txt"
COUNT="$("$PENDING/generate-halide-aot" "$PENDING" --macos --count)"
RESEARCH_COUNT="$(python3 -c 'import json; d=json.load(open("Sources/FotufilmHalide/aot-variants.json"))["wavefront_experiment"]; print(len(d["variants"])*(len(d["bands"])+1))')"
seq "$((COUNT-RESEARCH_COUNT))" "$((COUNT-1))" | xargs -P "${FOTUFILM_AOT_JOBS:-2}" -I{} \
  "$PENDING/generate-halide-aot" "$PENDING" --macos "--variant={}"
ACTUAL="$(find "$PENDING" -maxdepth 1 -name '*_wavefront_*.a' | wc -l | tr -d ' ')"
[[ "$ACTUAL" == "$RESEARCH_COUNT" ]]
# Publish identity only after every archive and header is present and the source stayed fixed.
[[ "$(cat "$PENDING/source-key.txt")" == "$(python3 tools/aot-release.py key macos)" ]]
cp "$PENDING"/*.a "$PENDING"/*.h "$OUTPUT/"
cp "$PENDING/generate-halide-aot" "$OUTPUT/"
mv "$PENDING/source-key.txt" "$OUTPUT/source-key.txt"
echo "Verified $ACTUAL macOS research trace kernels: $OUTPUT"
