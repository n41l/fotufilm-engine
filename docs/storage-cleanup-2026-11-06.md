# Experiment results and storage cleanup — 2026-11-06

Latest experiment is stage26, MTF pointwise fusion × unchanged BestFit pool. Raw report and all arm medians rechecked:16 valid processes, **10794** measured requests. The human Markdown summary said10466; the original machine-readable results already said10794. Corrected that prose only, without changing raw measurements or JSON evidence.25/25 pixel comparisons pass; source/JIT proof and stage24/25/26 report hashes match their recorded values.

| Arm | Median ms | Maximum measured Metal peak MiB |
| --- | ---: | ---: |
| Original R | 46.042 | 1183.719 |
| MTF | 42.150 | 1071.719 |
| BestFit | 43.299 | 991.719 |
| MTF + BestFit | 39.943 | 1031.719 |

COMBO is13.25% faster and152MiB below original in this single UHD campaign; pool-only remains40MiB lower in peak. These are within-campaign observations, not universal stability or release acceptance. The proposed cause of overlapping savings is not independently proven by this cleanup audit. Candidate3/Print MTF was tested in stage25 with no confirmed benefit; it is no longer unimplemented. Defaults stay off; pending gates and current uncommitted source/report/tool changes are preserved.

Disk became completely full during initial inspection; the first manifest write failed after one rebuildable runner object removal. That one path/size could not be recorded. The subsequent complete object index records419 further driver/shim/adapter/wrappers objects,32.04MiB, deleted only under this candidate build directory. No final executable, AOT library, source, input, report or analysis was deleted by this object cleanup.

Cleanup completed:

- Delete the rebuildable link objects above; build commands/source metadata retained.
- 832 exact-byte duplicate archive/library paths deduplicated through APFS copy-on-write clones,772.77MiB logical duplicate contents. These are independent files, not hard links; historical SHA and paths stay unchanged. Logical duplicate size is not a physical disk-recovery measurement.
- 1549 raw numeric-frame/resource-trace/pool-attempt/JSONL log files losslessly gzipped;506.21MiB size reduction. Every gzip was fully decompressed and raw SHA verified before removing the uncompressed copy. Reports, summaries, analyses and image inputs remain readable and uncompressed.
- 128 archives sharing identical bytes after the first64KiB deduplicated using APFS clones; each original prefix restored and **entire original compressed SHA** verified before atomic replacement.1039.42MiB duplicate suffix contents shared; original gzip hashes and paths remain valid.

Existing task Python processes were checked by working directory and belonged to other projects; no benchmark/compiler process was seen. User services and other project caches were not changed. Only this task candidate/build directory was cleaned. Final free space observed here:1.89GiB; it fluctuates with other system activity. Reserve1GiB again before future experiments.

Full per-path recovery/deletion indices, including hashes:

- build/cleanup-2026-11-06.json
- build/cleanup-2026-11-06-clones.json
- build/cleanup-2026-11-06-raw-archives.json
- build/cleanup-2026-11-06-archive-clones.json

To restore a raw log/frame, locate its raw path in raw-archives.json, decompress the named gzip into a temporary sibling, check the recorded raw_sha256, then rename it to the raw path. Preserve the gzip if desired. No restoration is needed for CoW-deduplicated files; contents and paths are unchanged. Use fresh build output directories when regenerating experiments. No code was rebuilt and no benchmark was run during this cleanup.

Post-cleanup verification: stage24/25/26 evidence hashes unchanged; all16 stage26 score records valid;10794 request total and each arm median agree with the raw report; every CoW replacement and stored gzip hash matches its index. Source/tool changes from the other agent remain uncommitted and untouched. No unrelated changes were staged or committed.
