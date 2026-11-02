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
Krell v2.0 development tree (WP1 vector lowering; x86_64 native lane).
The C reference here is clang, not gcc: the opponent changed with
the machine, and every number below is from this one run.

Best ns per call (lower is faster):

| kernel | C -O0 | C -O1 | C -O2 | Krell native | Krell interp | Python | NumPy |
|---|---|---|---|---|---|---|---|
| fill32 | 706.0K | 328.1K | 66.3K | 66.5K | 291.97M | 15.76M | 63.8K |
| span | 14.7K | 6.1K | 6.1K | 58.4K | 2.18M | 1.16M | 29.7K |
| sumsq | 1.18M | 529.4K | 420.1K | 425.0K | 306.30M | 47.28M | 371.2K |
| fib | 13.79M | 5.95M | 6.38M | 14.21M | 4.07G | 211.76M | -- |
| histo | 3.67M | 1.38M | 1.17M | 4.94M | 1.45G | 93.26M | 6.39M |
| fnv1a | 9.87M | 5.26M | 5.26M | 7.94M | 1.25G | 407.92M | -- |

## Reading the results

- fill32 is at parity with clang -O2 (ratio 1.002 in this harness
  run; a tuned unroll/access sweep reached 0.992, S = 1.008). Both
  implementations move 4 MiB at ~64 GB/s -- the memory-bandwidth
  roofline of the machine. There is no headroom left in this
  domain for either side. Krell v1.1 measured 24.3x behind C on
  this kernel and machine class; the gain came from vector
  lowering in the optimizer (WP1), not from kernel changes -- the
  kernels are byte-identical to the v1 run.
- sumsq is at parity (1.012; the sweep reached 1.000). Krell now
  emits the same instruction sequence clang does for the i64
  reduction; beating it requires a different sequence, which is
  superoptimizer work (WP3), not tuning.
- The remaining gaps are the unworked domains: span 9.64x
  (gather + fixed-point pipeline), histo 4.21x (read-modify-write
  scatter), fib 2.23x (call overhead), fnv1a 1.51x (serial chain).
  Register allocation, addressing-mode selection, and fragment
  superoptimization are the scheduled mechanisms (WP2/WP3).
- Headline: the geometric mean of S = T_C / T_Krell across the six
  kernels is 0.44 on this run (44% of C speed overall), up from
  0.18 for v1.1 measured the same way on this machine class.
- On the original bench machine (AMD EPYC, gcc -O2), the same
  v2.0 toolchain measured fill32 at 0.313x and sumsq at 0.569x
  vs C -O2 -- ahead of C -- because gcc's baseline-target
  vectorization leaves headroom that clang on this machine does
  not. Both statements are true; they are measurements of
  different opponents, which is why the machine and compiler are
  stated with every table.

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
