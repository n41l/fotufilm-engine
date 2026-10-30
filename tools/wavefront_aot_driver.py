"""Build external AOT call instrumentation without editing the reference engine.

Only the shim translation unit sees aliases. Each wrapper records the exact
selected frame symbol and calls its original generated archive function. Both
benchmark arms must use the same driver and instrumentation version.
"""
from pathlib import Path
import re
import subprocess
import sys


def build(repo, kernels, out, driver, *, definitions=()):
    repo, kernels, out, driver = (Path(p).resolve() for p in (repo, kernels, out, driver))
    out.mkdir(parents=True, exist_ok=True)
    if not (kernels / ".generated-from").is_file():
        raise ValueError("reference AOT generation must finish before building a runner")
    source_key = subprocess.check_output(
        [sys.executable, str(repo / "tools/aot-release.py"), "key", "macos"], text=True).strip()
    if (kernels / ".generated-from").read_text().split()[0] != source_key:
        raise ValueError("AOT source/configuration fingerprint does not match this checkout")
    wrappers = ['#include <cstdio>',
                'extern "C" { extern const char *fotufilm_bench_actual_variant; '
                'extern int fotufilm_bench_aot_calls; extern int fotufilm_bench_trace_variants; }']
    aliases = []
    for header in sorted(kernels.glob("fotufilm_halide_ios_*.h")):
        name = header.stem
        if not any(name.startswith("fotufilm_halide_ios_" + kind)
                   for kind in ("color", "monochrome", "no_film")):
            continue
        signature = re.search(r"\bint\s+" + re.escape(name) + r"\((.*?)\);",
                              header.read_text(), re.S)
        if not signature:
            raise ValueError(f"missing frame signature: {header}")
        arguments = signature.group(1)
        names = [re.search(r"([A-Za-z_]\w*)\s*$", part).group(1)
                 for part in arguments.split(",")]
        aliases.append(f"#define {name} wavefront_trace_{name}")
        wrappers.append(f'#include "{header.name}"')
        wrappers.append(f'extern "C" int wavefront_trace_{name}({arguments}) {{\n'
                        f'  fotufilm_bench_actual_variant = "{name}";\n'
                        '  ++fotufilm_bench_aot_calls;\n'
                        f'  if (fotufilm_bench_trace_variants) std::fprintf(stderr, "AOT_VARIANT {name}\\n");\n'
                        f'  return {name}({", ".join(names)});\n}}')
    (out / "aliases.h").write_text("\n".join(aliases) + "\n")
    (out / "wrappers.cpp").write_text("\n".join(wrappers) + "\n")
    common = ["xcrun", "clang++", "-std=c++17", "-O2", "-DFOTUFILM_HALIDE_IOS_AOT=1",
              "-DFOTUFILM_AOT_WINDOWED_HOST=1", *definitions,
              "-target", "arm64-apple-macos14.0", f"-I{kernels}",
              f"-I{repo}/Sources/FotufilmHalide/include"]
    with (out / "build.log").open("w") as log:
        subprocess.run([*common, "-include", str(out / "aliases.h"), "-c",
                        str(repo / "Sources/FotufilmHalide/FotufilmHalideIOS.cpp"),
                        "-o", str(out / "shim.o")], check=True, stdout=log, stderr=log)
        subprocess.run([*common, str(driver), str(out / "wrappers.cpp"), str(out / "shim.o"),
                        *map(str, sorted(kernels.glob("*.a"))), "-framework", "Metal",
                        "-framework", "Foundation", "-o", str(out / "runner")],
                       check=True, stdout=log, stderr=log)
    return out / "runner"
