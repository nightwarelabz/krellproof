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
| fill32 | 1.23M | 556.6K | 292.4K | 86.7K | 153.74M | 28.49M | 277.5K |
| span | 22.9K | 13.3K | 14.4K | 9.2K | 1.81M | 2.11M | 76.5K |
| sumsq | 1.83M | 717.8K | 847.7K | 478.0K | 164.97M | 56.78M | 1.12M |
| fib | 17.25M | 16.80M | 4.81M | 9.66M | 2793.06M | 391.94M | -- |
| histo | 6.67M | 2.25M | 2.23M | 2.21M | 761.44M | 174.19M | 14.51M |
| fnv1a | 8.87M | 8.87M | 8.84M | 8.89M | 683.26M | 516.03M | -- |
| dot | 1.89M | 762.1K | 757.5K | 776.0K | 199.83M | 79.94M | 1.14M |
| saxpy | 2.23M | 737.5K | 721.5K | 260.4K | 211.19M | 128.21M | 474.6K |
| copy | 1.60M | 574.0K | 558.7K | 566.8K | 169.07M | 39.44M | 149.1K |
| bytesum | 5.18M | 2.44M | 2.21M | 2.95M | 651.59M | 108.06M | 3.41M |
| parse | 2.33M | 1.09M | 1.03M | 1.66M | 476.61M | 19.77M | -- |
| mix | 3.42M | 1.85M | 1.83M | 2.09M | 251.41M | 603.74M | 2.85M |

## Reading the results

- WP5 added six kernels in domains the original six did not
  cover: a two-stream reduction (dot), a fused multiply-add
  stream (saxpy), pure data movement (copy), a widening byte
  reduction (bytesum), a branchy text scan (parse), and a wide
  multiply chain (mix). The WP5 tail then closed the two
  domains that trailed. saxpy (2.241 in the WP5 run) runs at
  0.361: the loop vectorizer learned the map shape -- two
  input streams, an invariant multiplier, one output stream --
  and now lowers it to vector load/multiply/add/store with a
  scalar remainder loop, the same construction the fill and
  reduce shapes already used. parse (2.268) runs at 1.606: the
  optimizer now recognizes the range-check idiom
  (x >= lo) & (x <= hi) and rewrites it to the single
  subtract-and-unsigned-compare form (x - lo) <=u (hi - lo).
  parse still trails C -O2; its remaining gap is a register
  allocator spill of the loaded byte across the digit branch,
  which is future work, as is mix (1.141).
- bytesum's row in this run (1.335) is measurement context,
  not code: its emitted code is byte-identical to the WP5
  run's (0.987), its C -O2 time is unchanged, and repeated
  isolated runs of this run's own bench binary measure
  ~2.23M ns (ratio ~1.00). Streaming kernels on this shared
  host read high when a full bench run coincides with host
  load; dot shows the same wobble (0.906 in the WP5 run,
  1.024 here, on unchanged code generation).
- Headline for this run: the geometric mean of S = T_C / T_Krell
  is 1.293 across the original six kernels and 1.145 across
  all twelve, up from 1.226 and 0.968 in the WP5 run on this
  same machine -- the saxpy fix alone moved the twelve-kernel
  figure from below parity to ahead. On the previous recorded
  run (WP4, Apple M1 under Rosetta, clang 21) the original six
  measured a geomean S of 1.108, up from 1.002 after WP3,
  0.804 after WP2, and 0.44 after WP1. The two machines
  measure different opponents and are not directly comparable
  kernel by kernel.
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
