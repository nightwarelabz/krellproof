# KRELLPROOF

An assault stress bench for Krell-compiled code. Twelve small kernels --
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
| dot | 1M i64 pairs | multiply-accumulate reduction, two streams |
| saxpy | 1M i32, y = 3x + y | fused multiply-add stream (integer) |
| copy | 1M u32 stream copy | pure data movement |
| bytesum | 4M byte sum | byte-load reduction / widening |
| parse | 1M chars, sum of decimal integers | branchy state-machine scan |
| mix | 1M u64 splitmix64 | wide integer multiply chain |

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
  none (the kernel is recursion itself), fnv1a has none (the
  kernel is a serial dependency chain), and parse has none (the
  kernel is a stateful scan); all three are reported as absent,
  not approximated.

## Protocol

Warmup, then 7 rounds of a rep loop per kernel; best and median
per-call nanoseconds are recorded (Python fib: 3 rounds). The C and
Krell-native rows come from a single harness binary per C opt level,
so both sides of each comparison share buffers, protocol, and clock.

## Results (2026-11-02, v2.0 branch, WP5 run)

Run on the bench machine: AMD EPYC 9D25, gcc 13.3 -O2, Krell
v2.0 tree (WP1-WP5). Best per-call nanoseconds from
`results/results.json`:

| kernel | C -O0 | C -O1 | C -O2 | Krell | Krell interp | Python | NumPy |
|---|---|---|---|---|---|---|---|
| fill32 | 1.24M | 556.9K | 281.2K | 93.2K | 230.53M | 28.50M | 282.5K |
| span | 23.1K | 13.4K | 12.9K | 9.3K | 2.83M | 2.21M | 77.6K |
| sumsq | 1.84M | 719.0K | 761.5K | 476.4K | 241.80M | 78.25M | 1.14M |
| fib | 17.24M | 16.97M | 4.90M | 9.84M | 3189.12M | 548.70M | -- |
| histo | 6.72M | 2.25M | 2.25M | 2.22M | 749.27M | 248.88M | 14.20M |
| fnv1a | 8.89M | 9.72M | 8.90M | 8.86M | 707.96M | 749.18M | -- |
| dot | 1.90M | 765.6K | 802.8K | 727.2K | 195.95M | 85.35M | 1.19M |
| saxpy | 2.23M | 726.7K | 733.4K | 1.64M | 212.34M | 178.90M | 581.2K |
| copy | 1.60M | 571.1K | 570.2K | 568.5K | 167.83M | 47.49M | 182.1K |
| bytesum | 5.20M | 2.24M | 2.25M | 2.22M | 612.00M | 120.55M | 3.41M |
| parse | 2.34M | 1.08M | 1.05M | 2.39M | 474.82M | 21.81M | -- |
| mix | 3.45M | 1.89M | 1.91M | 2.10M | 248.40M | 637.65M | 3.51M |

## Reading the results

- WP5 adds six kernels in domains the original six did not
  cover: a two-stream reduction (dot), a fused multiply-add
  stream (saxpy), pure data movement (copy), a widening byte
  reduction (bytesum), a branchy text scan (parse), and a wide
  multiply chain (mix). First measurements on this machine:
  dot is ahead of C -O2 in its debut (0.906), copy and bytesum
  are at parity (0.997, 0.987), and mix is close (1.100).
  Two kernels trail and are the WP5 follow-up work: saxpy
  (2.241) -- gcc vectorizes the i32 multiply-add stream and
  the Krell optimizer does not yet -- and parse (2.268), whose
  per-byte branch chain has no specialized lowering yet.
- Headline for this run: the geometric mean of S = T_C / T_Krell
  is 1.226 across the original six kernels and 0.968 across
  all twelve -- the two trailing WP5 kernels are what pull the
  twelve-kernel figure under 1. On the previous recorded run
  (WP4, Apple M1 under Rosetta, clang 21) the original six
  measured a geomean S of 1.108, up from 1.002 after WP3,
  0.804 after WP2, and 0.44 after WP1. The two runs measure
  different opponents and are not directly comparable kernel
  by kernel.
- fill32 on this machine is not roofline-bound the way it was
  on the M1 run: the vectorized Krell store loop (93.2K) runs
  about 3x faster than gcc -O2's (281.2K), which did not
  vectorize the u32 store stream on this target. On the M1
  both sides sat at the ~64 GB/s memory roofline (WP4 ratio
  1.004) -- same kernels, different binding constraint.
- WP3 (fragment superoptimization) and WP4 (call, loop, and
  chain overhead polish) are recorded with the WP4 run: WP4
  took fib from 1.543 to 0.929 and fnv1a from 1.158 to 0.999
  against the WP3 run on that harness, with fill32, span, and
  sumsq code generation byte-identical between the WP3 and
  WP4 toolchains (their movement between those two Mac runs
  was variance, verified by emitted-code comparison and
  repeated timing). On this EPYC/gcc run fib measures 2.009;
  the earlier WP4-toolchain run on this same machine measured
  1.816, and the kernel remains the bench's most
  variance-sensitive row.
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

    kernels/    the twelve kernels: .krell sources + refs.c
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
  The recorded run for this branch was made on an AMD EPYC host
  (native x86_64, gcc 13.3); the previous recorded run (WP4) was
  made under Rosetta on an Apple M1 with clang 21, and the two
  tables measure different opponents -- a kernel's ratio moving
  between them is not, by itself, a regression or a gain.

## License

Apache-2.0, as with Krell itself.
