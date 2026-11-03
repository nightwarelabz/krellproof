#!/bin/bash
# KRELLPROOF full run: build, bench, validate, graph.
# Requires: a built krellc (Krell v1.1 tree), cc, python3 with numpy + PIL.
#   KRELLC=/path/to/krellc ./run.sh
set -e
cd "$(dirname "$0")"
KRELLC="${KRELLC:-$HOME/workspace/rung-runfix/krellc}"
export KRELL_TARGETS="${KRELL_TARGETS:-$(dirname "$KRELLC")/targets}"
mkdir -p build results
KERNELS="fill32 span sumsq fib histo fnv1a dot saxpy copy bytesum parse mix"

for k in $KERNELS; do
  "$KRELLC" parse kernels/$k.krell -o build/$k.krel
  "$KRELLC" build build/$k.krel --target x86_64 -O -o build/$k.s
  cc -O2 -c build/$k.s -o build/$k.o
  cat kernels/$k.krell harness/drivers/${k}_main.krell > build/drv_$k.krell
done

for O in 0 1 2; do
  cc -O$O -std=c11 -c kernels/refs.c -o build/refs_o$O.o
  cc -O$O -std=c11 -DIMPL_NAME="\"c_o$O\"" -o build/bench_o$O \
     harness/bench.c build/refs_o$O.o \
     build/fill32.o build/span.o build/sumsq.o build/fib.o \
     build/histo.o build/fnv1a.o build/dot.o build/saxpy.o \
     build/copy.o build/bytesum.o build/parse.o build/mix.o -lm
  ./build/bench_o$O > results/raw_c_o$O.jsonl
done

# WP6: the LLVM lane under the same protocol. Kernels are lowered to
# LLVM IR by krellc and compiled by clang -O2; the harness binary is
# built with KRELL_ONLY so it emits only the krell_llvm rows (the C
# reference rows come from bench_o2; checksums are still verified
# inside the binary against the linked C references).
LLVM_OBJS=""
for k in $KERNELS; do
  "$KRELLC" build build/$k.krel --target llvm -O -o build/${k}_llvm.ll
  clang -O2 -c build/${k}_llvm.ll -o build/${k}_llvm.o 2>/dev/null
  LLVM_OBJS="$LLVM_OBJS build/${k}_llvm.o"
done
cc -O2 -std=c11 -DKRELL_ONLY -DKRELL_IMPL_NAME='"krell_llvm"' -DIMPL_NAME='"c_o2"' \
   -o build/bench_llvm harness/bench.c build/refs_o2.o $LLVM_OBJS -lm
./build/bench_llvm > results/raw_krell_llvm.jsonl

python3 harness/bench.py python
python3 harness/bench.py interp
python3 harness/bench.py merge

python3 graph/gen_graph.py
"$KRELLC" parse graph/graph.krell -o build/graph.krel
"$KRELLC" build build/graph.krel --target x86_64 -O -o build/graph.s
cc build/graph.s -lm -o build/graph
./build/graph > build/graph.ppm
python3 -c "from PIL import Image; Image.open('build/graph.ppm').save('graph/graph.png')"
echo "done: results/results.json, graph/graph.png"
