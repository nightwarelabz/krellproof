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

## Results (2026-11-02)

Machine: AMD EPYC 9D25 126-Core Processor (4 cores visible) -
cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 - Python 3.12.3 - NumPy 1.26.4 -
Krell v1.1 (x86_64 native lane).

Best ns per call (lower is faster):

| kernel | C -O0 | C -O1 | C -O2 | Krell native | Krell interp | Python | NumPy |
|---|---|---|---|---|---|---|---|
| fill32 | 1.24M | 558.5K | 292.5K | 1.69M | 154.08M | 29.04M | 282.7K |
| span | 23.9K | 13.4K | 13.0K | 91.5K | 1.79M | 2.13M | 78.6K |
| sumsq | 2.25M | 733.1K | 744.3K | 2.84M | 170.56M | 57.78M | 1.13M |
| fib | 17.76M | 17.34M | 5.26M | 21.19M | 2.88G | 413.97M | -- |
| histo | 6.71M | 2.27M | 2.27M | 10.48M | 734.08M | 177.90M | 30.58M |
| fnv1a | 9.06M | 8.95M | 9.01M | 11.28M | 672.37M | 555.99M | -- |

## Reading the results

- On the serial dependency chain (fnv1a), where no optimizer can
  help, Krell native runs at 1.25x C -O2 -- near the latency floor.
- Where gcc's optimizer and vectorizer do the heavy lifting
  (fill32, span, sumsq, histo), Krell native trails C -O2 by
  3.8x-7.1x and sits in the C -O0 class. The current x86_64 backend
  is a direct code generator; closing this gap is backend work
  (vectorized lowering, better register use), not language work --
  the same Krell modules are the input either way.
- Krell native is 13x-26x faster than pure Python on the loop
  kernels, and on span it runs in NumPy's class (93 us vs 79 us)
  with scalar code.
- The interpreter is a correctness reference, not a runtime:
  60x-550x off C -O2. It still edges out CPython on span.
- NumPy's fill beats C -O2 (0.97x) because it is a tuned memset;
  its histogram is slower than Krell native (bincount overhead on
  this workload), which is a reminder that vectorized libraries
  have their own cliffs.

The deterministic property no column can show: the Krell rows are
produced by a total, verified IR whose outputs are byte-identical
across the x86_64, AArch64, RISC-V, and LLVM backends -- the same
checksum agreement this bench enforces between languages holds
between Krell targets by construction.

## Reproduce

Requires a built `krellc` from the Krell v1.1 tree, `cc`, and
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
- Timings are from a shared virtual machine and are best read as
  ratios between implementations measured minutes apart, not as
  absolute hardware numbers.

## License

Apache-2.0, as with Krell itself.
