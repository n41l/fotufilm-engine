# Isolated whole-frame general kernel experiments

This private Mac experiment ports four scheduling optimizations independently:
register placement (1), normalized-reduction fusion (2), analytical valid-cell
counting (4), and radius-one Gaussian specialization (8). Mask0 is the matched
current-source control. Masks are explicit construction/build policy, never an
environment default or public packed configuration. Nonzero masks enter the
JIT cache identity; zero retains the previous key. Other backends and the
original windowed policy are unchanged.

The generator accepts `--general-optimizations=N` only for one explicit Mac
color/monochrome float-realtime general variant, without wavefront. Graph/Stages,
precision, boundaries, global coordinates, feature gating and the C ABI remain
unchanged. The radius-one arm retains separate data/weight reductions at larger
radii, so it does not silently enable the normalized arm. Register placement
retains the original producer policy for existing wavefront research graphs.

Each arm replaces exactly two named existing general archives in a hash-checked
frozen legacy control. Its identity records source key, mask and archive hashes.
The external instrumentation records the actual frame symbol, one AOT call and
GPU dispatches. There is no window loop, explicit row cache or new host wait.
This composite is diagnostic, not a complete current-source release stamp.

`prepare-general-optimizations.py` builds G0 and four individual arms. The pixel
verifier compares four frozen cases directly against independent R-B0, retains
R-B1 as a separate proof, and checks actual whole-frame execution. The history
verifier runs one complete14-frame process per arm, comparing each completed
frame against independently saved hashed R frames before deleting successful
dumps. Still/exact legacy classes stay frozen and are marked inactive for the
new general archives; frame11 is the preexisting wavefront-only injected failure
and is not part of this general14-frame sequence. No new host cache/fault API is
introduced.

The timing cohort is R-B0, G0, registers, normalized, counted, radius1, R-B1,
rotated by two positions for each frozen case. Each arm gets a fresh process,
5s warmup /30s measurement /2s tail /5s idle, one frame in flight and1GiB pool.
Normal own-arm hashes, actual symbols, one-call accounting and dispatch counts
must match independent proofs. One round/arm/case cannot freeze B_ref or pass
release, memory/retention or upstream performance gates. All failures and
unfavorable rows remain; no default switch, Taggii integration or speedup PR.
