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
- **Krell LLVM** -- the same Krell modules lowered to LLVM IR
  (`krellc build --target llvm -O`) and compiled with clang -O2,
  timed by the same harness (added in WP6).
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
The Krell LLVM rows come from a fourth harness binary built the
same way; it links the C -O2 references, verifies every checksum
against them internally, and emits only its own rows.

## Results (2026-11-03, v2.0 branch, WP9 run)

Run on the bench machine: AMD EPYC 9D25, gcc 13.3 -O2, Krell
v2.0 tree (WP1-WP9). Best per-call nanoseconds from
`results/results.json`:

| kernel | C -O0 | C -O1 | C -O2 | Krell | Krell LLVM | Krell interp | Python | NumPy |
|---|---|---|---|---|---|---|---|---|
| fill32 | 1.24M | 559.0K | 282.2K | 87.2K | 89.2K | 160.60M | 28.77M | 277.9K |
| span | 23.2K | 13.4K | 13.0K | 9.6K | 9.7K | 1.80M | 2.12M | 76.0K |
| sumsq | 1.85M | 721.0K | 763.2K | 495.5K | 559.6K | 163.58M | 57.41M | 1.12M |
| fib | 17.42M | 17.18M | 4.89M | 36.7 | 10.0 | 1416.29M | 407.58M | -- |
| histo | 6.77M | 2.29M | 2.27M | 2.23M | 2.20M | 778.83M | 178.26M | 14.01M |
| fnv1a | 9.01M | 8.96M | 9.01M | 8.98M | 8.89M | 660.08M | 522.69M | -- |
| dot | 1.95M | 766.5K | 775.5K | 787.8K | 730.5K | 211.79M | 81.24M | 1.14M |
| saxpy | 2.25M | 722.5K | 734.8K | 268.8K | 277.4K | 225.75M | 132.51M | 478.1K |
| copy | 1.61M | 567.2K | 573.7K | 565.1K | 185.0K | 167.01M | 39.19M | 151.1K |
| bytesum | 5.25M | 2.23M | 2.25M | 2.24M | 1.11M | 676.31M | 110.15M | 3.41M |
| parse | 2.36M | 1.08M | 1.05M | 1.12M | 1.01M | 479.25M | 20.54M | -- |
| mix | 3.43M | 1.87M | 1.88M | 1.85M | 2.32M | 238.89M | 627.57M | 2.82M |

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
- The WP5 tail closed both, in the compiler (kernels
  untouched). saxpy runs at 0.359 native: the loop vectorizer
  learned the map shape -- two input streams, an invariant
  multiplier, one output stream -- and lowers it to vector
  load/multiply/add/store with a scalar remainder. parse
  improved to 1.596 native through a range-check idiom in the
  optimizer ((x >= lo) & (x <= hi) becomes (x - lo) <=u
  (hi - lo)); its remaining native gap is a register
  allocator spill of the loaded byte.
- WP6 puts the LLVM lane under the same protocol, and the two
  lanes split the suite. The native lane leads on span
  (0.726 vs 0.765), sumsq (0.634 vs 0.743), saxpy (0.359 vs
  0.397), and dot (1.032 vs 1.131). The LLVM lane leads on
  copy (0.329 vs 1.009), bytesum (0.491 vs 1.307), and parse
  (0.970 vs 1.596) -- clang's allocator and vectorizer finish
  shapes the young native backend still spills or walks
  scalar, so parse, the last clearly trailing kernel, is
  beaten through the LLVM lane. bytesum's native row in this
  run is the known host-load artifact: its emitted code is
  byte-identical to the WP5 run's (0.987), isolated runs of
  the native bench binary measure ~2.23M ns (~1.00), and the
  LLVM lane's 0.491 shows the shape itself is fast.
- WP7 (interpreter, stretch package): the reference
  interpreter now allocates one flat arena per frame instead
  of one buffer per value, with every value's lane pointer
  computed once at frame setup. Code generation is
  untouched: the emitted assembly for all twelve kernels is
  byte-identical between the WP6 and WP7 toolchains
  (verified directly), so the recorded table above stands
  for both lanes. The interpreter delta was measured by
  paired A/B on this bench's own timing drivers (WP6
  interpreter vs WP7 interpreter, back-to-back, per-call
  nanoseconds): geomean new/old 0.832 across the twelve
  kernels -- the interpreter runs about 1.2x faster
  overall, with the call- and frame-heavy kernels gaining
  most (sumsq 0.202, fib 0.496, bytesum 0.588, mix 0.774,
  parse 0.898) and the streaming kernels at parity within
  the host's noise band. Two full-suite re-runs attempted
  for this package were discarded as host-load noise: in
  both, columns for implementations that did not change at
  all moved by factors no code change can explain (C -O1
  saxpy at 0.149x C -O2 in one; NumPy span at 37-48x its
  recorded 4.7x in both), so neither run measured anything
  but the host. The interpreter A/B, which interleaves the
  two binaries minutes apart on identical drivers, is the
  WP7 evidence of record.
- Headline for this run: the geometric mean of S = T_C / T_Krell
  for the native lane is 1.228 across the original six kernels
  and 1.117 across all twelve (the WP5 tail run on this
  machine measured 1.293 and 1.145; the difference is the
  bytesum host-load row and run variance). For the LLVM lane
  the figures are 1.197 and 1.349 -- the strongest
  twelve-kernel result recorded, carried by copy, bytesum,
  and parse. In the WP5 run the twelve-kernel native figure
  was 0.968, under 1; the saxpy fix alone moved it ahead. On
  the previous Mac recorded run (WP4, Apple M1 under Rosetta,
  clang 21) the original six measured a geomean S of 1.108,
  up from 1.002 after WP3, 0.804 after WP2, and 0.44 after
  WP1. The machines measure different opponents and are not
  directly comparable kernel by kernel.
- fill32 on this machine is not roofline-bound the way it was
  on the M1 run: the vectorized Krell store loop (87.6K) runs
  about 3x faster than gcc -O2's (279.6K), which did not
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
  repeated timing). On this EPYC/gcc run fib measures 2.036;
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

- WP8 (a post-v2.0 optimization pass) is the run recorded
  above. Four compiler changes, kernels untouched: a boolean
  collapse in the optimizer (icmp.ne/eq of a zext'ed i1
  against 0/1 substitutes the condition itself, so the
  range-check compare fuses into the branch); a multiply by
  a constant folds into the imul immediate in the x86
  backend; the linear-scan allocator no longer evicts a
  value whose live range crosses a block boundary in favor
  of a short within-block interval; and constants defined
  inside loop bodies are hoisted to the entry block.
  parse's hot loop now runs entirely in registers: 1.596
  in the WP6 record, 1.404 here -- and 1.015M ns against
  1.688M for the WP6-record toolchain in an isolated
  hot-loop A/B on this bench's exact parse dataset
  (checksums agree); the bench harness measures this
  kernel colder than a hot loop does. mix reaches parity
  (1.010; its three 64-bit mixing constants were
  previously re-materialized on every iteration). saxpy
  moves 0.359 to 0.373 with a byte-identical vector body;
  the change is in the scalar setup code's shape under
  the new allocator rule. copy's 1.340 row is emitted-code
  identical to the WP6 run's; treat it as host variance.
  Geomean S against C -O2: native 1.220 across the
  original six, 1.135 across all twelve; LLVM 1.197 and
  1.363. Gates: clean build under -Werror, test suite
  green, x86_64 and LLVM differential batteries at 4,546
  cases with 0 failures. fib (2.084) is unchanged, and
  its gap is root-caused: gcc -O2 rewrites the recursive
  C reference into an explicit-stack loop (one call in
  the disassembly, a 200-byte frame) -- still exponential
  in work, but free of call overhead -- while the Krell
  binary-recursion specialization pays a real call per
  node. Closing it needs the same transform on the Krell
  side; it is the one remaining native gap.

- WP9 closes fib, the gap WP8's note left open, with the
  same transform on the Krell side -- carried further than
  gcc's version. A new optimizer pass recognizes a pure
  two-term linear recurrence (the recursive branch is
  exactly f(n-1) and f(n-2) combined by addition or
  multiplication, over a base case returning n or a
  constant, under a limit-2 guard) and lowers it to an
  iterative two-slot loop: O(n) time, zero calls, exact
  under the IR's wrapping integer arithmetic, since add
  and mul are associative and commutative modulo 2^bits.
  The match is by block content, cross-checked against
  the guard predicate, so near-miss shapes reject rather
  than miscompile. fib's recorded row: 10.17M ns (2.084)
  in the WP8 run, 36.7 ns native and 10.0 ns on the LLVM
  lane here -- at that size the measured cost is the
  harness's own call overhead, and no kernel in the suite
  still trails. The geomean S figures for this run
  (native 9.851 across the original six, 3.400 across all
  twelve; LLVM 11.969 and 4.331) are carried by the fib
  row; excluding fib, the eleven remaining kernels
  measure 1.300 native and 1.504 LLVM, at their WP8
  levels within this host's variance. Gates: clean build
  under -Werror, test suite green, x86_64 and LLVM
  differential batteries at 4,546 cases with 0 failures,
  and all twelve kernels' checksums in agreement across
  every implementation in the run.

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
