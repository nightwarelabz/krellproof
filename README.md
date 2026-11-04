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

## Results (2026-11-03, v2.0 branch, WP15 run)

Run on the bench machine: AMD EPYC 9D25, gcc 13.3 -O2, Krell
v2.0 tree (WP1-WP15). The LLVM lane of this run was built
with clang 18 (the emscripten-bundled clang 19 used for the
WP8-WP11 records was lost with its VM image); the lane's
differential battery passes 4,546/0 under it. Best per-call
nanoseconds from `results/results.json`:

| kernel | C -O0 | C -O1 | C -O2 | Krell | Krell LLVM | Krell interp | Python | NumPy |
|---|---|---|---|---|---|---|---|---|
| fill32 | 1.25M | 560.5K | 278.4K | 86.4K | 96.1K | 142.94M | 28.53M | 279.6K |
| span | 23.0K | 13.4K | 12.8K | 8.7K | 9.8K | 1.91M | 2.15M | 76.0K |
| sumsq | 1.83M | 718.0K | 759.6K | 401.1K | 567.5K | 162.04M | 60.05M | 1.12M |
| fib | 17.30M | 17.36M | 4.84M | 24.7 | 10.1 | 1338.31M | 421.01M | -- |
| histo | 6.75M | 2.26M | 2.26M | 2.23M | 2.22M | 755.51M | 178.15M | 15.23M |
| fnv1a | 9.02M | 9.04M | 8.89M | 8.91M | 8.92M | 662.30M | 520.67M | -- |
| dot | 1.91M | 781.5K | 759.8K | 563.0K | 423.6K | 203.88M | 81.46M | 1.24M |
| saxpy | 2.23M | 724.3K | 730.8K | 193.2K | 279.3K | 201.97M | 131.29M | 525.8K |
| copy | 1.61M | 566.8K | 568.2K | 186.9K | 190.2K | 166.03M | 39.53M | 158.6K |
| bytesum | 5.25M | 2.23M | 2.23M | 647.5K | 602.3K | 637.17M | 110.98M | 3.41M |
| parse | 2.37M | 1.09M | 1.05M | 977.9K | 1.02M | 484.25M | 20.14M | -- |
| mix | 3.51M | 1.85M | 1.87M | 1.88M | 2.17M | 248.94M | 611.01M | 2.91M |

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

- WP10 removes the edge move from loop-carried updates,
  in the register allocator (shared backend kit, kernels
  untouched). A value whose only use is as the branch
  argument for a block parameter is now computed directly
  into that parameter's register when the parameter has
  no later use in the source block -- the accumulator and
  index updates of a loop body land in place instead of
  in a fresh register plus a copy on the back edge. The
  coalesced register is protected from eviction, and at
  most one value per block and register coalesces. parse,
  the kernel built from such updates, improves from
  1.068 in the WP9 run to 1.023 here, and in an
  interleaved A/B of the WP9 and WP10 bench binaries it
  measures at parity with C -O2 (1.041M ns against
  1.040M). fib's loop narrows further, 36.7 to 24.7 ns.
  dot's loop body is shorter by the same change but
  measures 1.060 here: its cost is the accumulator
  dependency chain, not the removed move, and the row
  moves with code layout on this host. Geomean S against
  C -O2: native 10.457 across the original six, 3.483
  across all twelve (1.289 excluding fib); LLVM 11.842
  and 4.231 (1.468 excluding fib). Gates: clean build
  under -Werror, test suite green, x86_64 and LLVM
  differential batteries at 4,546 cases with 0 failures,
  and all twelve kernels' checksums in agreement across
  every implementation in the run.

- WP11 teaches the loop vectorizer the pure data-movement
  shape, in the optimizer (kernels untouched). A two-stream
  loop whose body is one load and one store of the loaded
  value -- copy's shape -- previously fell between the
  existing classes: the map class requires a multiply-add,
  and the generic scan rejects any body with two pointer
  computations. The new class rides the map layout (vector
  steps with a scalar remainder) and emits no arithmetic.
  copy's native row moves from 1.005 in the WP10 run to
  0.331 here, level with the LLVM lane's 0.331; a first
  WP11 run on this host measured 0.297. A companion
  two-stream reduction class (dot's shape: multiply the
  two streams, accumulate) is implemented behind a
  profitability gate: it fires only when the element type
  has real vector lanes, because the 64-bit form takes
  the scalar-unroll path, whose unrolled body keeps both
  pointers and all accumulators live at once and the
  native allocator spills (an ungated build measured dot
  at 1.825 native, against 0.556 on the LLVM lane, whose
  allocator holds the shape). With the gate, dot's code
  generation is unchanged from WP10 and its rows move
  only with this host's variance, as do parse's (0.939
  native here). Geomean S against C -O2: native 10.504
  across the original six, 3.869 across all twelve
  (1.445 excluding fib); LLVM 11.906 and 4.263 (1.479
  excluding fib). Gates: clean build under -Werror, test
  suite green, x86_64 and LLVM differential batteries at
  4,546 cases with 0 failures, AArch64 and RISC-V code
  generation verified, and all twelve kernels' checksums
  in agreement across every implementation in the run.

- WP12 teaches the loop vectorizer the widening reduction,
  in the optimizer (kernels untouched). A loop that loads
  a narrow integer element, zero-extends it, and adds it
  into a wider accumulator -- bytesum's shape -- was
  rejected by every existing class because of the zext
  between the load and the add. The new class rides the
  scalar reduce layout: four independent load/zext/add
  accumulator chains with a scalar remainder, the
  accumulator carried at its full width end to end.
  Byte-for-byte comparison of the WP11 and WP12 compilers'
  output across all twelve kernels shows bytesum is the
  only kernel whose code generation changes. Its in-run
  row here is 1.010, unchanged from WP11: under this
  harness's protocol the 4 MiB stream is bound by the
  scalar byte-load path, and repeated full runs read the
  row at parity for both compilers. Measured hot, in an
  interleaved A/B on the bench's own 4 MiB workload
  (WP11-compiled against WP12-compiled bytesum, checksums
  identical), the new body runs 1.51M ns against 2.24M --
  the gain is real but the protocol cannot see it; the
  LLVM lane's 0.501 comes from true vector widening,
  which remains the open native-side lever for this
  kernel. Two rows in this run are host weather, not
  signal: span's C -O2 row read high (16.3K against its
  usual 12.7K), flattering span's native ratio, and the
  LLVM lane's mix row (1.454) is this run's outlier.
  Geomean S against C -O2: native 10.821 across the
  original six, 3.931 across all twelve (1.473 excluding
  fib); LLVM 12.334 and 4.313 (1.498 excluding fib).
  Gates: clean build under -Werror, test suite green,
  x86_64 and LLVM differential batteries at 4,546 cases
  with 0 failures, AArch64 and RISC-V code generation
  verified, and all twelve kernels' checksums in
  agreement across every implementation in the run.

- WP13 gives the widening reduction its SWAR form, in
  the optimizer (kernels untouched). Where the WP12
  class unrolls byte-at-a-time chains, the SWAR form
  loads one accumulator-width word per step and sums
  its elements in-register: one mask/shift level folds
  element pairs into fields of twice the element width,
  then a multiply by the field-replicated one collects
  the field sums into the top field. The reduction is
  exact on any endianness: fields are mask-isolated
  before every add, and every partial field sum is
  bounded by fields * 2 * (2^E - 1) < 2^(2E), so no
  carry ever crosses a field boundary. The class runs
  one word with one accumulator: past that, the native
  allocator spills the reduction chain's intermediates
  (measured on this kernel: one word 0.84M ns, two
  words 1.00M, four words 1.41M). bytesum's native row
  moves from 1.010 in the WP12 run to 0.378 here, and
  the LLVM lane's from 0.501 to 0.268 -- the word form
  also compiles better through clang than the byte
  loop it previously auto-vectorized. Correctness was
  checked independently of the bench: four buffer
  patterns (all-ones, random, ramp, zeros) across 26
  lengths including every word/tail boundary match the
  C reference exactly. Geomean S against C -O2: native
  10.492 across the original six, 4.200 across all
  twelve (1.582 excluding fib); LLVM 11.844 and 4.559
  (1.590 excluding fib). Gates: clean build under
  -Werror, test suite green, x86_64 and LLVM
  differential batteries at 4,546 cases with 0 failures,
  AArch64 and RISC-V code generation verified, and all
  twelve kernels' checksums in agreement across every
  implementation in the run.

- WP14 works on the native register allocator and one
  missed optimizer shape (kernels untouched). The
  allocator's linear scan now chooses spill victims by
  Belady's rule -- evict the interval whose next use is
  farthest -- with next uses taken from a per-value use
  census recorded on the same position grid as the
  interval bounds (the census previously recorded each
  use one position early, which made an operand of the
  very instruction being allocated for look already
  spent and therefore evictable) and, for a value live
  across a loop back edge, wrapped to the first use of
  the next iteration. In the optimizer, a general
  integer map class joins the vectorizer: one indexed
  load, a pure integer chain over the loaded value, one
  indexed store -- the saxpy shape generalized past
  multiply-add -- with a new vector logical-shift-right
  op (vlshr) carried by all four backends for the
  chains that need it. Chains containing a 64-bit
  multiply are gated out: the native lane's decomposed
  i64 vector multiply costs more than the scalar chain,
  so mix's emitted code is byte-identical to WP13's.
  Native rows move: saxpy 0.369 to 0.259, bytesum 0.378
  to 0.285, sumsq 0.643 to 0.524, parse 0.997 to 0.911.
  An interleaved A/B against the WP13 compiler (five
  rounds, medians of per-round bests) measures saxpy
  -28.7%, bytesum -23.6%, sumsq -18.2%, span -12.4%,
  parse -0.3%; this run's dot (0.988) and mix (1.038)
  native rows and mix's LLVM row (1.159) are host
  weather on byte-identical code -- the A/B reads dot
  -3.9% and mix -0.9%, and mix's LLVM IR is unchanged.
  The LLVM lane is otherwise flat (1.590 to 1.580
  excluding fib): WP14's work is native-side. Geomean
  S against C -O2: native 10.973 across the original
  six, 4.542 across all twelve (1.720 excluding fib);
  LLVM 11.856 and 4.532 (1.580 excluding fib). Gates:
  clean build under -Werror, test suite green, x86_64
  and LLVM differential batteries at 4,546 cases with
  0 failures, AArch64 and RISC-V code generation
  verified, fuzz parity with WP13 unchanged, and all
  twelve kernels' checksums in agreement across every
  implementation in the run.

- WP15 is a correctness pass first and a performance pass
  second (kernels untouched). Nine shipped bug classes were
  reproduced, fixed, and covered by new reproducers: the
  x86_64 early-return specialization skipped materializing
  entry constants and compared narrow parameters at full
  ABI width (a recursive i32 fib driven from C crashed on
  negative inputs); the vector unsigned-divide op fell
  through to the multiply path when its operands were
  register-resident; the scalarized vector path read slot
  offsets of register-resident operands (offset 0, the
  saved frame); extracting an f32 vector lane above 0 read
  the extraction scratch register instead of the source;
  AArch64 and RISC-V addressed every vector through slot
  offset 0 because the shared allocator register-allocates
  single-unit vectors those backends treat as
  memory-resident, and their emitters lacked the
  dead-value filter the x86_64 emitter has always had, so
  dead block arguments were moved over the saved frame;
  an AArch64 lane load used the value register as the
  address base for the second operand. The deepest was in
  the shared allocator's liveness: when a backend folds an
  instruction into its consumer (an address computation
  into a load/store addressing mode), the folded value's
  operands are read at the consumer, but liveness recorded
  their uses at the folded instruction, so a value defined
  in between could take the operand's register and the
  consumer read the wrong address -- the root cause of
  the long-standing fuzz seed 1 crash and seed 2 memory
  mismatches. Liveness now expands folded uses recursively
  at every census site. With these fixes the AArch64 and
  RISC-V differential batteries run under emulation and
  pass 4,546/0 for the first time (previous records
  verified code generation only), and the fuzzer is clean
  on all four backends. The performance change is one
  gate: the two-stream reduction class now fires for i64
  elements, taking the scalar-unroll body whose register
  pressure the WP14 Belady allocator holds spill-free;
  the gate had excluded i64 since a pre-Belady spill
  measurement. dot moves from 0.988 to 0.741 native and
  from 0.951 to 0.558 on the LLVM lane (per-call Krell
  time over C -O2 time);
  a v2i64 vector body for the same shape was measured and
  rejected (about 9% slower than the unroll -- the
  decomposed 64-bit vector multiply costs more than four
  independent scalar multiply chains). An interleaved A/B
  against the WP14 compiler confirms dot -23.5% native
  and -44.3% LLVM with all other kernels within host
  noise; dot's absolute times vary by bench process on
  this host (array layout), so the ratios are the stable
  reading. Geomean S against C -O2: native 11.020 across
  the original six, 4.651 across all twelve (1.766
  excluding fib); LLVM 11.618 and 4.690 (1.643 excluding
  fib). Gates: clean build under -Werror, test suite
  green, all four differential batteries at 4,546 cases
  with 0 failures (AArch64 and RISC-V executed under
  qemu), fuzz clean on x86_64 seeds 1-7 and on seed 2 for
  AArch64, RISC-V, and LLVM, and all twelve kernels'
  checksums in agreement across every implementation in
  the run.

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
