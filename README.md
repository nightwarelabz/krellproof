# KRELLPROOF

An assault stress bench for Krell-compiled code. Six small kernels --
the shapes that show up inside real systems code -- are implemented
identically in Krell, C, and Python, timed head-to-head on one machine,
and required to produce byte-identical results before any number is
believed.

The comparison chart is itself a Krell program: `graph/graph.krell`
(reads no input; every pixel, bar, gridline, and glyph is computed by
Krell from the bench results baked into its data tables).

![KRELLPROOF results](graph/graph.png)

## Kernels

| kernel | workload | shape under test |
|---|---|---|
| fill32 | 1M u32 stores | streaming stores / vectorizer bait |
| span | 4096 px textured span | serial fixed-point pipeline + gather |
| sumsq | 1M i64 multiply-accumulate | reduction loop |
| fib | fib(32), naive recursion | raw call overhead |
| histo | 4M byte histogram | load-increment-store, data-dependent |
| fnv1a | 4M byte FNV-1a | serial dependency chain (latency floor) |

The C references in `kernels/refs.c` define the semantics. Every
implementation of a kernel must produce the same checksum
(sum/value over the output, defined per kernel in the harness);
the merger refuses to publish a table when any checksum disagrees.

## Implementations

- **C -O0 / -O1 / -O2** -- `kernels/refs.c` compiled with gcc at each
  level, timed by `harness/bench.c`.
- **Krell native** -- `kernels/*.krell`, built with
  `krellc build --target x86_64 -O`, linked into the same harness.
- **Krell interp** -- the same Krell modules run by the reference
  interpreter (`krellc run`) through driver mains in
  `harness/drivers/`. Timed with a two-point slope: each driver runs
  at two rep counts and the per-call cost is the difference quotient,
  which cancels process startup and buffer setup exactly.
- **Python** -- pure-Python implementations (no library help).
- **NumPy** -- vectorized forms where an honest one exists. fib has
  none (the kernel is recursion itself) and fnv1a has none (the
  kernel is a serial dependency chain); both are reported as absent,
  not approximated.

## Protocol

Warmup, then 7 rounds of a rep loop per kernel; best and median
per-call nanoseconds are recorded (Python fib: 3 rounds). The C and
Krell-native rows come from a single harness binary per C opt level,
so both sides of each comparison share buffers, protocol, and clock.

## Results (2026-11-02, v2.0 branch)

Machine: Apple M1 (x86_64 binaries under Rosetta) -
Apple clang 21.0.0 -O2 - Python 3.15.1 - NumPy 2.5.4 -
Krell v2.0 development tree (WP1 vector lowering; WP2 x86_64 backend
code generation; WP3 fragment superoptimization of hot inner loops;
WP4 call, loop, and chain overhead polish; x86_64 native lane).
The C reference here is clang, not gcc: the opponent changed with
the machine, and every number below is from this one run.

Best ns per call (lower is faster):

| kernel | C -O0 | C -O1 | C -O2 | Krell native | Krell interp | Python | NumPy |
|---|---|---|---|---|---|---|---|
| fill32 | 729.5K | 327.8K | 66.1K | 66.3K | 273.47M | 15.78M | 63.4K |
| span | 14.7K | 6.1K | 6.1K | 5.5K | 2.27M | 1.16M | 29.5K |
| sumsq | 1.18M | 521.3K | 419.0K | 270.0K | 292.51M | 45.22M | 367.8K |
| fib | 13.79M | 5.95M | 6.37M | 5.92M | 4.17G | 211.24M | -- |
| histo | 3.65M | 1.40M | 1.17M | 1.17M | 1.49G | 93.16M | 6.35M |
| fnv1a | 9.87M | 5.26M | 5.26M | 5.26M | 1.24G | 384.31M | -- |

## Reading the results

- fill32 remains in the memory-roofline band (ratio 1.044 in
  this harness run). Both implementations move 4 MiB at ~64 GB/s
  -- the memory-bandwidth roofline of the machine. There is no
  headroom left in this domain for either side. Krell v1.1
  measured 24.3x behind C on this kernel and machine class; the
  gain came from vector lowering in the optimizer (WP1), not
  from kernel changes -- the kernels are byte-identical to the
  v1 run.
- WP3 (fragment superoptimization of the hot inner loops) put
  three kernels ahead of clang -O2. span runs at ratio 0.739
  (S = 1.353x): a proved value-preserving rewrite of the 24-bit
  per-pixel RGB lighting pipeline -- one 16-bit packed multiply
  replacing three scalar multiplies -- lowered to a zero-spill
  SSE2 sequence, 9.55x faster than the v1.1 baseline Krell time.
  sumsq runs at 0.725 (S = 1.379x): the scalar reduction is
  replaced by four independent accumulator streams with a
  balanced pairwise tree reduction at loop exit, 5.27x over
  baseline -- the beat-C attempt transferred here from WP1 is
  closed. histo runs at 0.989 (S = 1.011x): 4-way unrolling
  with all four byte loads issued before any increment
  (memory-level parallelism), plus zero-extension/truncation
  register coalescing that removes the intermediate moves,
  4.66x over baseline.
- WP3 also carried a register-allocation and ABI correctness
  overhaul: dead intervals (defpos == endpos == 0) no longer
  evict live arguments, moves into unallocated slots can no
  longer overwrite the saved frame pointer at [rbp - 0], and
  constant rematerialization (func_rebuild_constants) folds
  immediates back into instructions. The differential battery
  stands at 4,546 cases, 0 failures, and every checksum is
  unchanged.
- WP4 (call, loop, and chain overhead polish) closed the two
  gaps WP3 left, against the WP3 run on this same harness as
  baseline. fib runs at 0.929 (WP3: 1.543): the x86_64 backend
  recognizes the binary self-recursion shape, converts the
  second recursive call into an accumulation loop, and returns
  base cases without building a frame -- sound because Krell
  integer addition is total and associative, and the battery
  and checksums are unchanged. fnv1a runs at 0.999 (WP3:
  1.158): the optimizer recognizes the serial hash chain,
  unrolls it four ways, and hoists the FNV prime constant out
  of the loop into a dedicated register, where clang materializes
  it once and the previous Krell code materialized it per byte.
  histo is at parity (0.998; WP3: 0.989) with its inner-loop
  spill removed. WP4 changes no code generation for fill32,
  span, or sumsq -- their emitted code is byte-identical to the
  WP3 toolchain -- so their movement against the WP3 run
  (fill32 1.044 -> 1.004, span 0.739 -> 0.902, sumsq 0.725 ->
  0.644) is run-to-run variance on a shared machine, not
  software change, in either direction.
- Headline: the geometric mean of S = T_C / T_Krell across the
  six kernels is 1.108 on this run, up from 1.002 after WP3,
  0.804 after WP2, 0.44 after WP1, and 0.235 for the v1.1
  baseline measured the same way on this machine class. Krell
  is ahead of clang -O2 overall on this bench; every kernel is
  at or ahead of parity in this run, with fill32 bounded by
  the memory roofline rather than by code generation.
- On the original bench machine (AMD EPYC, gcc -O2), an
  independent run of the same WP4 toolchain measured fill32
  at 0.312x, span at 0.742x, sumsq at 0.807x, fib at 1.816x,
  histo at 0.980x, and fnv1a at 1.015x vs C -O2, with every
  checksum identical to the Mac run. The two machines disagree
  on individual kernels -- they are measurements of different
  opponents (gcc on EPYC vs clang under Rosetta on M1), which
  is why the machine and compiler are stated with every table.
- Chart rendering note: the first WP3 build rendered this
  chart's glyph text fragmented. The cause was a register-pool
  change in the x86_64 backend that admitted RCX and RDX as
  allocatable registers when a function contained no division
  or no variable shift -- but the emitter uses RCX for every
  non-constant shift and RDX for memcpy/memset argument setup
  regardless, so live values in those registers were clobbered
  (the chart's data accessors were the first code to hit it;
  all bench checksums were unaffected). The pool is restored
  to the WP2 set in the current v2.0 tree, and this chart is
  rendered by the fixed toolchain from the recorded results
  above.

The deterministic property no column can show: the Krell rows are
produced by a total, verified IR whose outputs are byte-identical
across the x86_64, AArch64, RISC-V, and LLVM backends -- the same
checksum agreement this bench enforces between languages holds
between Krell targets by construction.

## Reproduce

Requires a built `krellc` from the Krell v2.0 branch tree, `cc`, and
Python 3 with NumPy and Pillow:

    KRELLC=/path/to/krellc ./run.sh

Outputs: `results/results.json` (merged, validated) and
`graph/graph.png` (rendered by the generated Krell chart program;
`graph/gen_graph.py` lays out the scene from `results.json`).

## Layout

    kernels/    the six kernels: .krell sources + refs.c
    harness/    bench.c (native timing), bench.py (Python + interp
                timing, merge + validation), drivers/ (interp mains)
    graph/      gen_graph.py + generated graph.krell + graph.png
    results/    raw per-runner JSONL + merged results.json
    run.sh      one-command end-to-end run

## Notes

- `graph/gen_graph.py` documents a surface-parser behavior found
  while building the chart: a chained-condbr selector function
  (dataptr dispatch) trips a verifier dominance error at chain
  depth >= 2 in the v1.1 toolchain, so the chart uses per-blob
  specialized accessors. Minimal repros were confirmed before the
  workaround was adopted.
- Timings are best read as ratios between implementations measured
  minutes apart on one machine, not as absolute hardware numbers.
  The recorded run for this branch was made under Rosetta on an
  Apple M1 (x86_64 binaries); both sides of every comparison were
  translated identically.

## License

Apache-2.0, as with Krell itself.
