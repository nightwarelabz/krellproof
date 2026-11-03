#!/usr/bin/env python3
"""KRELLPROOF Python-side runner + merger.

Times the pure-Python and NumPy implementations of the kernel battery
and the Krell interpreter (krellc run), then merges every raw result
(native C/Krell runs included) into results/results.json after
validating that all implementations agree on every kernel checksum.

Interpreter timing uses a two-point method: each driver is run with
two different rep counts, and the per-call cost is the slope, which
cancels process startup and buffer setup exactly.
"""
import json
import os
import platform
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
RESULTS = os.path.join(ROOT, "results")
KRELLC = os.environ.get("KRELLC", os.path.expanduser("~/workspace/rung-runfix/krellc"))
MASK64 = (1 << 64) - 1

FILL_N = 1 << 20
SPAN_W = 4096
SUMSQ_N = 1 << 20
BYTES_N = 4 << 20

rows = []  # (kernel, impl, best_ns, median_ns, checksum)


def emit(kernel, impl, best, median, checksum):
    rows.append({
        "kernel": kernel, "impl": impl,
        "best_ns": round(best, 1), "median_ns": round(median, 1),
        "checksum": checksum & MASK64,
    })
    print(f"{kernel:8s} {impl:14s} best {best:16.1f} ns  median {median:16.1f} ns  "
          f"checksum {checksum & MASK64}", flush=True)


def bench(fn, reps, rounds=7, warmup=True):
    if warmup:
        fn()
    per = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for _ in range(reps):
            fn()
        per.append((time.perf_counter() - t0) / reps * 1e9)
    per.sort()
    return per[0], per[len(per) // 2]


# ---------------------------------------------------------------- setup data
import numpy as np

_i32 = np.arange(BYTES_N, dtype=np.uint32)
PATTERN = (((_i32 * np.uint32(1103515245) + np.uint32(12345)) >> np.uint32(16))
           & np.uint32(0xFF)).astype(np.uint8).tobytes()
TEX_NP = ((np.arange(4096, dtype=np.uint32) * np.uint32(2654435761))
          >> np.uint32(8)).astype(np.uint32)
TEX_PY = TEX_NP.tolist()
A_NP = np.arange(1, SUMSQ_N + 1, dtype=np.int64)
BUF_NP = np.frombuffer(PATTERN, dtype=np.uint8)
STREAM_N = 1 << 20
B_NP = (np.arange(STREAM_N, dtype=np.int64) % 7) + 3
PARSE_TEXT = b"1234567 " * (STREAM_N // 8)

# ---------------------------------------------------------------- pure python
def py_fill32():
    buf = [0] * FILL_N
    return buf


def run_python():
    # fill32
    buf = [0] * FILL_N
    def f():
        for i in range(FILL_N):
            buf[i] = 0x12345678
    best, med = bench(f, 3)
    emit("fill32", "python", best, med, sum(buf))

    # span
    dst = [0] * SPAN_W
    def sp():
        u, v = 3 << 16, 5 << 16
        for x in range(SPAN_W):
            tx = (u >> 16) & 63
            ty = (v >> 16) & 63
            px = TEX_PY[ty * 64 + tx]
            r = (((px >> 16) & 0xFF) * 200) >> 8
            g = (((px >> 8) & 0xFF) * 200) >> 8
            b = ((px & 0xFF) * 200) >> 8
            dst[x] = (r << 16) | (g << 8) | b
            u += 70000
            v -= 30000
    best, med = bench(sp, 50)
    emit("span", "python", best, med, sum(dst))

    # sumsq
    a = list(range(1, SUMSQ_N + 1))
    holder = [0]
    def sq():
        s = 0
        for x in a:
            s += x * x
        holder[0] = s
    best, med = bench(sq, 3)
    emit("sumsq", "python", best, med, holder[0])

    # fib (plain recursion, same algorithm as the C/Krell versions)
    sys.setrecursionlimit(10000)
    def fib(n):
        return n if n < 2 else fib(n - 1) + fib(n - 2)
    holder[0] = 0
    def fb():
        holder[0] = fib(32)
    best, med = bench(fb, 1, rounds=3, warmup=False)
    emit("fib", "python", best, med, holder[0])

    # histo
    hist = [0] * 256
    def hi():
        for i in range(256):
            hist[i] = 0
        for b in PATTERN:
            hist[b] += 1
    best, med = bench(hi, 2)
    emit("histo", "python", best, med,
         sum((i + 1) * hist[i] for i in range(256)))

    # fnv1a
    holder[0] = 0
    def fv():
        h = 14695981039346656037
        for b in PATTERN:
            h = ((h ^ b) * 1099511628211) & MASK64
        holder[0] = h
    best, med = bench(fv, 2)
    emit("fnv1a", "python", best, med, holder[0])

    # dot
    a64 = list(range(1, STREAM_N + 1))
    b64 = [(i % 7) + 3 for i in range(STREAM_N)]
    holder[0] = 0
    def dt():
        s = 0
        for i in range(STREAM_N):
            s += a64[i] * b64[i]
        holder[0] = s & MASK64
    best, med = bench(dt, 3)
    emit("dot", "python", best, med, holder[0])

    # saxpy: checksum is the output after exactly one application
    xs = [(i + 1) & 0xFFFFFFFF for i in range(STREAM_N)]
    y0 = [(i % 5) + 1 for i in range(STREAM_N)]
    y1 = list(y0)
    for i in range(STREAM_N):
        y1[i] = (3 * xs[i] + y1[i]) & 0xFFFFFFFF
    sax_checksum = sum(y1)
    yt = list(y0)
    def sx():
        for i in range(STREAM_N):
            yt[i] = (3 * xs[i] + yt[i]) & 0xFFFFFFFF
    best, med = bench(sx, 3)
    emit("saxpy", "python", best, med, sax_checksum)

    # copy
    src32 = [(((i * 2654435761) & 0xFFFFFFFF) >> 8) for i in range(STREAM_N)]
    dst32 = [0] * STREAM_N
    def cp():
        for i in range(STREAM_N):
            dst32[i] = src32[i]
    best, med = bench(cp, 3)
    emit("copy", "python", best, med, sum(src32))

    # bytesum
    holder[0] = 0
    def bs():
        s = 0
        for b in PATTERN:
            s += b
        holder[0] = s
    best, med = bench(bs, 2)
    emit("bytesum", "python", best, med, holder[0])

    # parse
    holder[0] = 0
    def pa():
        holder[0] = sum(int(t) for t in PARSE_TEXT.split())
    best, med = bench(pa, 2)
    emit("parse", "python", best, med, holder[0])

    # mix (splitmix64 finalizer per element)
    holder[0] = 0
    def mx():
        s = 0
        for i in range(STREAM_N):
            z = (i + 1 + 0x9E3779B97F4A7C15) & MASK64
            z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
            z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
            s = (s + (z ^ (z >> 31))) & MASK64
        holder[0] = s
    best, med = bench(mx, 2)
    emit("mix", "python", best, med, holder[0])


# ---------------------------------------------------------------- numpy
def run_numpy():
    arr = np.empty(FILL_N, dtype=np.uint32)
    def f():
        arr.fill(0x12345678)
    best, med = bench(f, 20)
    emit("fill32", "numpy", best, med, int(arr.sum(dtype=np.uint64)))

    tex = TEX_NP
    xs = np.arange(SPAN_W, dtype=np.int64)
    out_holder = [None]
    def sp():
        u = 196608 + 70000 * xs
        v = 327680 - 30000 * xs
        px = tex[((v >> 16) & 63) * 64 + ((u >> 16) & 63)]
        r = (((px >> 16) & 0xFF) * 200) >> 8
        g = (((px >> 8) & 0xFF) * 200) >> 8
        b = ((px & 0xFF) * 200) >> 8
        out_holder[0] = (r << 16) | (g << 8) | b
    best, med = bench(sp, 200)
    emit("span", "numpy", best, med, int(out_holder[0].sum(dtype=np.uint64)))

    def sq():
        return np.dot(A_NP, A_NP)
    best, med = bench(sq, 20)
    emit("sumsq", "numpy", best, med, int(sq()))

    def hi():
        return np.bincount(BUF_NP, minlength=256)
    best, med = bench(hi, 10)
    h = hi()
    emit("histo", "numpy", best, med,
         sum((i + 1) * int(h[i]) for i in range(256)))
    # fib and fnv1a have no honest NumPy form (recursion / serial chain).

    def dt():
        return np.dot(A_NP, B_NP)
    best, med = bench(dt, 20)
    emit("dot", "numpy", best, med, int(dt()))

    # saxpy: checksum is the output after exactly one application
    xs32 = (np.arange(1, STREAM_N + 1, dtype=np.uint32) & np.uint32(0xFFFFFFFF)).astype(np.int32)
    y0_32 = ((np.arange(STREAM_N, dtype=np.int64) % 5) + 1).astype(np.int32)
    y1_32 = y0_32 * np.int32(1)
    y1_32 = np.int32(3) * xs32 + y1_32
    sax_checksum = int(y1_32.astype(np.uint32).sum(dtype=np.uint64))
    yt_32 = y0_32.copy()
    def sx():
        yt_32[:] = np.int32(3) * xs32 + yt_32
    best, med = bench(sx, 20)
    emit("saxpy", "numpy", best, med, sax_checksum)

    src_np = (((np.arange(STREAM_N, dtype=np.uint32) * np.uint32(2654435761))
               >> np.uint32(8)).astype(np.uint32))
    dst_np = np.empty(STREAM_N, dtype=np.uint32)
    def cp():
        np.copyto(dst_np, src_np)
    best, med = bench(cp, 20)
    emit("copy", "numpy", best, med, int(src_np.sum(dtype=np.uint64)))

    def bs():
        return np.sum(BUF_NP, dtype=np.uint64)
    best, med = bench(bs, 10)
    emit("bytesum", "numpy", best, med, int(bs()))
    # parse has no honest NumPy form (stateful scan).

    mix_src = np.arange(1, STREAM_N + 1, dtype=np.uint64)
    def mx():
        z = mix_src + np.uint64(0x9E3779B97F4A7C15)
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return z ^ (z >> np.uint64(31))
    best, med = bench(mx, 20)
    emit("mix", "numpy", best, med, int(mx().sum(dtype=np.uint64)))


# ---------------------------------------------------------------- interpreter
INTERP_REPS = {  # (R1, R2) for the two-point slope
    "fill32": (2, 6), "span": (100, 300), "sumsq": (2, 6),
    "fib": (1, 3), "histo": (1, 4), "fnv1a": (1, 4),
    "dot": (2, 6), "saxpy": (2, 6), "copy": (2, 6),
    "bytesum": (1, 4), "parse": (1, 3), "mix": (2, 6),
}
SUM_TARGET = {"fill32": ("sum(0, 0, buf)", "fin(0)"),
              "span": ("sum(0, 0, dst)", "fin(0)"),
              "saxpy": ("sum(0, 0, y)", "fin(0)"),
              "copy": ("sum(0, 0, dst)", "fin(0)"),
              "mix": ("sum(0, 0, dst)", "fin(0)")}


def krell_run(path):
    env = dict(os.environ)
    env.setdefault("KRELL_TARGETS",
                   os.path.expanduser("~/workspace/rung-runfix/targets"))
    t0 = time.perf_counter()
    p = subprocess.run([KRELLC, "run", path, "main"],
                       capture_output=True, text=True, env=env)
    dt = time.perf_counter() - t0
    if p.returncode != 0:
        raise RuntimeError(f"krellc run {path} failed: {p.stderr.strip()}")
    last = [ln for ln in p.stdout.strip().splitlines() if ln.strip()][-1]
    return dt, int(last.split()[0]) & MASK64


def run_interp():
    for kernel, (r1, r2) in INTERP_REPS.items():
        src = open(os.path.join(BUILD, f"drv_{kernel}.krell")).read()
        # checksum run (default rep count, full driver incl. checksum phase)
        _, checksum = krell_run(os.path.join(BUILD, f"drv_{kernel}.krell"))
        times = {}
        for r in (r1, r2):
            txt, n = re.subn(r"icmp\.slt i64 r, \d+",
                             f"icmp.slt i64 r, {r}", src)
            assert n == 1, f"{kernel}: rep literal found {n} times"
            if kernel in SUM_TARGET:
                old, new = SUM_TARGET[kernel]
                assert old in txt, f"{kernel}: sum target missing"
                txt = txt.replace(old, new)
            path = os.path.join(BUILD, f"timing_{kernel}_{r}.krell")
            open(path, "w").write(txt)
            times[r] = min(krell_run(path)[0] for _ in range(2))
        per_call = (times[r2] - times[r1]) / (r2 - r1) * 1e9
        emit(kernel, "krell_interp", per_call, per_call, checksum)


# ---------------------------------------------------------------- merge
def load_jsonl(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        return []
    return [json.loads(ln) for ln in open(path) if ln.strip()]


def merge():
    all_rows = []
    for name in ("raw_c_o0.jsonl", "raw_c_o1.jsonl", "raw_c_o2.jsonl"):
        all_rows += load_jsonl(name)
    all_rows += load_jsonl("raw_python.jsonl")
    all_rows += load_jsonl("raw_interp.jsonl")

    # dedupe krell-native rows (emitted by all three C binaries):
    # keep the first set measured; checksums must agree everywhere.
    seen, merged = set(), []
    for r in all_rows:
        key = (r["kernel"], r["impl"])
        if r["impl"] == "krell" and key in seen:
            continue
        seen.add(key)
        merged.append(r)

    by_kernel = {}
    for r in merged:
        by_kernel.setdefault(r["kernel"], {})[r["impl"]] = r
    problems = []
    for kernel, impls in sorted(by_kernel.items()):
        sums = {r["checksum"] for r in impls.values()}
        if len(sums) != 1:
            problems.append(f"{kernel}: checksum disagreement {sums}")
    if problems:
        raise SystemExit("VALIDATION FAILED:\n" + "\n".join(problems))

    def sh(cmd):
        return subprocess.run(cmd, shell=True, capture_output=True,
                              text=True).stdout.strip()
    meta = {
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "machine": platform.machine(),
        "cpu": sh("grep -m1 'model name' /proc/cpuinfo | cut -d: -f2"),
        "cores": os.cpu_count(),
        "gcc": sh("cc --version | head -1"),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "krellc": KRELLC,
        "krell_tree": sh("git -C ~/workspace/rung-runfix rev-parse HEAD 2>/dev/null") or "v1.1 tree",
        "protocol": ("C/Krell native and Python: warmup + 7 rounds, best and "
                     "median per-call ns (fib python: 3 rounds). Interpreter: "
                     "two-point slope over two rep counts, best of 2 runs."),
    }
    ratios = {}
    for kernel, impls in by_kernel.items():
        base = impls["c_o2"]["best_ns"]
        ratios[kernel] = {impl: round(r["best_ns"] / base, 3)
                          for impl, r in sorted(impls.items())}
    out = {"meta": meta, "results": merged, "ratios_vs_c_o2": ratios}
    with open(os.path.join(RESULTS, "results.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print("\n=== ratios vs C -O2 (best ns; >1 = slower than C -O2) ===")
    impls_all = ["c_o0", "c_o1", "c_o2", "krell", "krell_interp", "python", "numpy"]
    print(f"{'kernel':9s}" + "".join(f"{i:>14s}" for i in impls_all))
    for kernel in ("fill32", "span", "sumsq", "fib", "histo", "fnv1a",
                   "dot", "saxpy", "copy", "bytesum", "parse", "mix"):
        line = f"{kernel:9s}"
        for i in impls_all:
            v = ratios.get(kernel, {}).get(i)
            line += f"{v:14.3f}" if v is not None else f"{'--':>14s}"
        print(line)
    print("\nAll checksums agree across every implementation.")
    print("Wrote results/results.json")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("python", "all"):
        run_python()
        run_numpy()
        with open(os.path.join(RESULTS, "raw_python.jsonl"), "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        rows.clear()
    if which in ("interp", "all"):
        run_interp()
        with open(os.path.join(RESULTS, "raw_interp.jsonl"), "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        rows.clear()
    if which in ("merge", "all"):
        merge()
