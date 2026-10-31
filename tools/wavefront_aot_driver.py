"""Build external AOT call instrumentation without editing the reference engine.

Only the shim translation unit sees aliases. Each wrapper records the exact
selected frame symbol and calls its original generated archive function. Both
benchmark arms must use the same driver and instrumentation version.
"""
from pathlib import Path
import os
import json
import hashlib
import re
import subprocess
import sys


def build(repo, kernels, out, driver, *, definitions=(), driver_definitions=(),
          adapter=None, adapter_definitions=(), trace_overrides=(), diagnostic_control=None, diagnostic_kernels=None,
          shim_definitions=(), resource_hooks=False, shim_suffix=None):
    repo, kernels, out, driver = (Path(p).resolve() for p in (repo, kernels, out, driver))
    out.mkdir(parents=True, exist_ok=True)
    if not (kernels / ".generated-from").is_file():
        raise ValueError("reference AOT generation must finish before building a runner")
    diagnostic_archives=[]
    if diagnostic_control:
        control=Path(diagnostic_control).resolve();manifest=json.loads((control/'control.json').read_text())
        if kernels!=control/'kernels':raise ValueError('diagnostic base must be the frozen C kernel directory')
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        for name,value in manifest['artifacts'].items():
            if digest(control/name)!=value:raise ValueError('frozen C control changed')
        for name,value in manifest['source'].items():
            if name.startswith(('Sources/FotufilmHalide/Stages/','Sources/FotufilmHalide/Graph/')) and digest(repo/name)!=value:
                raise ValueError('diagnostic experiment changed shared film expressions')
        diagnostic_kernels=Path(diagnostic_kernels).resolve()
        expected=subprocess.check_output([sys.executable,str(repo/'tools/aot-release.py'),'key','macos'],text=True).strip()
        if (diagnostic_kernels/'source-key.txt').read_text().strip()!=expected:raise ValueError('diagnostic kernel source changed')
        diagnostic_archives=sorted(diagnostic_kernels.glob('fotufilm_halide_ios_*_wavefront_*.a'))
        if len(diagnostic_archives)!=manifest.get('experimental_archive_count',12):raise ValueError('complete explicit producer/consumer kernel set required')
        (out/'diagnostic-build.json').write_text(json.dumps({'mixed_candidate_revisions':True,'performance_acceptance':False,
            'control_manifest_sha256':digest(control/'control.json'),'experimental_source_key':expected,
            'experimental_archives':{a.name:digest(a) for a in diagnostic_archives}},indent=2)+'\n')
    else:
        source_key = subprocess.check_output(
            [sys.executable, str(repo / "tools/aot-release.py"), "key", "macos"], text=True).strip()
        if (kernels / ".generated-from").read_text().split()[0] != source_key:
            raise ValueError("AOT source/configuration fingerprint does not match this checkout")
    trace_overrides=[Path(p).resolve() for p in trace_overrides]
    if trace_overrides:
        trace_key=subprocess.check_output([sys.executable,str(repo/'tools/aot-release.py'),'key','macos'],
            text=True,env={**os.environ,'FOTUFILM_AOT_WAVEFRONT_TRACE':'1'}).strip()
        if len({p.name for p in trace_overrides})!=len(trace_overrides):raise ValueError('duplicate trace override')
        for archive in trace_overrides:
            normal=next((p for p in diagnostic_archives if p.name==archive.name),kernels/archive.name)
            if not normal.is_file() or '_wavefront_' not in archive.name:
                raise ValueError('trace override must replace an existing research kernel')
            if (archive.parent/'source-key.txt').read_text().strip()!=trace_key:
                raise ValueError('trace override source/configuration identity changed')
            pattern=r'\bint\s+'+re.escape(archive.stem)+r'\((.*?)\);'
            signatures=[re.search(pattern,p.read_text(),re.S).group(1) for p in (
                archive.with_suffix('.h'),normal.with_suffix('.h'))]
            if signatures[0]!=signatures[1]:raise ValueError('trace override ABI changed')
    wrappers = ['#include <cstdio>',
                'extern "C" { extern const char *fotufilm_bench_actual_variant; '
                'extern int fotufilm_bench_aot_calls; extern int fotufilm_bench_trace_variants; }']
    if resource_hooks:
        wrappers += ['struct halide_buffer_t;',
            'extern "C" void wf_resource_aot_enter(const char *);',
            'extern "C" void wf_resource_aot_leave();',
            'extern "C" void wf_resource_bind(const char *, const char *, halide_buffer_t *);',
            'struct WfResourceScope { WfResourceScope(const char *n) { wf_resource_aot_enter(n); } ~WfResourceScope() { wf_resource_aot_leave(); } };']
    aliases = []
    headers={p.name:p for p in kernels.glob("fotufilm_halide_ios_*.h")}
    if diagnostic_archives:headers.update({p.name:p for p in diagnostic_kernels.glob("fotufilm_halide_ios_*.h")})
    for header in sorted(headers.values()):
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
        if resource_hooks:
            bindings=''.join(f'  wf_resource_bind("{name}", "{arg}", {arg});\n'
                for part,arg in zip(arguments.split(","),names) if 'halide_buffer_t' in part)
            wrappers.append(f'extern "C" int wavefront_trace_{name}({arguments}) {{\n'
                f'  fotufilm_bench_actual_variant = "{name}"; ++fotufilm_bench_aot_calls;\n'
                f'  WfResourceScope scope("{name}");\n'
                f'  const int result = {name}({", ".join(names)});\n'+bindings+'  return result;\n}')
            continue
        wrappers.append(f'extern "C" int wavefront_trace_{name}({arguments}) {{\n'
                        f'  fotufilm_bench_actual_variant = "{name}";\n'
                        '  ++fotufilm_bench_aot_calls;\n'
                        f'  if (fotufilm_bench_trace_variants) std::fprintf(stderr, "AOT_VARIANT {name}\\n");\n'
                        f'  return {name}({", ".join(names)});\n}}')
    (out / "aliases.h").write_text("\n".join(aliases) + "\n")
    (out / "wrappers.cpp").write_text("\n".join(wrappers) + "\n")
    common = ["xcrun", "clang++", "-std=c++17", "-O2", "-DFOTUFILM_HALIDE_IOS_AOT=1",
              "-DFOTUFILM_AOT_WINDOWED_HOST=1", *definitions,
              "-target", "arm64-apple-macos14.0",
              *([f"-I{diagnostic_kernels}"] if diagnostic_archives else []), f"-I{kernels}",
              f"-I{repo}/Sources/FotufilmHalide/include"]
    shim_source=repo / "Sources/FotufilmHalide/FotufilmHalideIOS.cpp"
    shim_quote=[]
    if shim_suffix:
        suffix=Path(shim_suffix).resolve()
        original=shim_source.read_bytes()
        generated=out/'diagnostic-shim.cpp'
        generated.write_bytes(original+b'\n'+suffix.read_bytes())
        shim_quote=['-iquote',str(shim_source.parent)]
        (out/'diagnostic-shim.json').write_text(json.dumps({
            'diagnostic_only':True,'original_sha256':hashlib.sha256(original).hexdigest(),
            'suffix_sha256':hashlib.sha256(suffix.read_bytes()).hexdigest(),
            'generated_sha256':hashlib.sha256(generated.read_bytes()).hexdigest(),
            'shim_definitions':list(shim_definitions),'resource_hooks':bool(resource_hooks)},indent=2)+'\n')
        shim_source=generated
    with (out / "build.log").open("w") as log:
        subprocess.run([*common, *shim_definitions, *shim_quote, "-include", str(out / "aliases.h"), "-c",
                        str(shim_source),
                        "-o", str(out / "shim.o")], check=True, stdout=log, stderr=log)
        subprocess.run([*common, *driver_definitions, '-c', str(driver), '-o', str(out/'driver.o')],
                       check=True, stdout=log, stderr=log)
        subprocess.run([*common, '-c', str(out/'wrappers.cpp'), '-o', str(out/'wrappers.o')],
                       check=True, stdout=log, stderr=log)
        objects=[out/'driver.o',out/'wrappers.o',out/'shim.o']
        if adapter:
            subprocess.run([*common,*adapter_definitions,'-c',str(adapter),'-o',str(out/'adapter.o')],
                           check=True,stdout=log,stderr=log)
            objects.append(out/'adapter.o')
        subprocess.run([*common, *map(str,objects),
                        *map(str,trace_overrides), *map(str,(a for a in diagnostic_archives if a.name not in {p.name for p in trace_overrides})),
                        *map(str, sorted(p for p in kernels.glob("*.a") if p.name not in {a.name for a in [*trace_overrides,*diagnostic_archives]})), "-framework", "Metal",
                        "-framework", "Foundation", "-o", str(out / "runner")],
                       check=True, stdout=log, stderr=log)
    return out / "runner"
