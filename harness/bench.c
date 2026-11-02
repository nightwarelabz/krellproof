/* KRELLPROOF assault harness (native side).
 * Times the C references (compiled at the -O level of this binary)
 * against the Krell-compiled kernels (krellc build -O, x86_64) under
 * one protocol: warmup, 7 rounds of a rep loop, best and median
 * per-call ns reported. Every kernel's output is verified byte-equal
 * between the C and Krell implementations before any timing is
 * trusted, and a checksum is printed for cross-runner comparison.
 * Output: one JSON object per line. */
#define _POSIX_C_SOURCE 199309L
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifndef IMPL_NAME
#define IMPL_NAME "c"
#endif

/* C references (kernels/refs.c) */
void ref_fill32(uint32_t *, int64_t, uint32_t);
void ref_span(uint32_t *, const uint32_t *, int64_t, int32_t, int32_t, int32_t, int32_t, int32_t);
int64_t ref_sumsq(const int64_t *, int64_t);
int64_t ref_fib(int64_t);
void ref_histo(const uint8_t *, int64_t, int64_t *);
uint64_t ref_fnv1a(const uint8_t *, int64_t);

/* Krell-compiled kernels */
void fill32(void *, int64_t, int32_t);
void span(void *, const void *, int64_t, int32_t, int32_t, int32_t, int32_t, int32_t);
int64_t sumsq(const void *, int64_t);
int64_t fib(int64_t);
void histo(const void *, int64_t, void *);
int64_t fnv1a(const void *, int64_t);

static double now_s(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

static int cmp_d(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

/* Run fn(reps) for 7 rounds; return best per-call ns, median via out. */
typedef void (*run_fn)(void *ctx, int reps);
static double bench(run_fn fn, void *ctx, int reps, double *median_out) {
    double per[7];
    fn(ctx, 1); /* warmup */
    for (int r = 0; r < 7; r++) {
        double t0 = now_s();
        fn(ctx, reps);
        per[r] = (now_s() - t0) / reps * 1e9;
    }
    qsort(per, 7, sizeof(double), cmp_d);
    *median_out = per[3];
    return per[0];
}

static void emit(const char *kernel, const char *impl, double best, double median,
                 unsigned long long checksum) {
    printf("{\"kernel\":\"%s\",\"impl\":\"%s\",\"best_ns\":%.1f,\"median_ns\":%.1f,"
           "\"checksum\":%llu}\n", kernel, impl, best, median, checksum);
    fflush(stdout);
}

static void die(const char *kernel, const char *what) {
    fprintf(stderr, "VERIFY FAIL %s: %s\n", kernel, what);
    exit(1);
}

/* ---------------- fill32 ---------------- */
#define FILL_N (1 << 20)
static uint32_t *fill_buf_a, *fill_buf_b;
static void run_fill_c(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) ref_fill32(fill_buf_a, FILL_N, 0x12345678u);
}
static void run_fill_k(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) fill32(fill_buf_b, FILL_N, 0x12345678);
}
static unsigned long long sum_u32(const uint32_t *b, int64_t n) {
    unsigned long long s = 0;
    for (int64_t i = 0; i < n; i++) s += b[i];
    return s;
}

/* ---------------- span ---------------- */
#define SPAN_W 4096
static uint32_t span_tex[4096], span_a[SPAN_W], span_b[SPAN_W];
static void run_span_c(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++)
        ref_span(span_a, span_tex, SPAN_W, 3 << 16, 5 << 16, 70000, -30000, 200);
}
static void run_span_k(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++)
        span(span_b, span_tex, SPAN_W, 3 << 16, 5 << 16, 70000, -30000, 200);
}

/* ---------------- sumsq ---------------- */
#define SUMSQ_N (1 << 20)
static int64_t *sumsq_a;
static void run_sumsq_c(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = ref_sumsq(sumsq_a, SUMSQ_N);
    (void)sink; (void)ctx;
}
static void run_sumsq_k(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = sumsq(sumsq_a, SUMSQ_N);
    (void)sink; (void)ctx;
}

/* ---------------- fib ---------------- */
static void run_fib_c(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = ref_fib(32);
    (void)sink; (void)ctx;
}
static void run_fib_k(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = fib(32);
    (void)sink; (void)ctx;
}

/* ---------------- byte kernels (histo, fnv1a) ---------------- */
#define BYTES_N (4 << 20)
static uint8_t *bytes_buf;
static int64_t hist_a[256], hist_b[256];
static void run_histo_c(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) {
        memset(hist_a, 0, sizeof hist_a);
        ref_histo(bytes_buf, BYTES_N, hist_a);
    }
}
static void run_histo_k(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) {
        memset(hist_b, 0, sizeof hist_b);
        histo(bytes_buf, BYTES_N, hist_b);
    }
}
static unsigned long long hist_checksum(const int64_t *h) {
    unsigned long long s = 0;
    for (int i = 0; i < 256; i++) s += (unsigned long long)(i + 1) * (unsigned long long)h[i];
    return s;
}
static void run_fnv_c(void *ctx, int reps) {
    volatile uint64_t sink;
    for (int i = 0; i < reps; i++) sink = ref_fnv1a(bytes_buf, BYTES_N);
    (void)sink; (void)ctx;
}
static void run_fnv_k(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = fnv1a(bytes_buf, BYTES_N);
    (void)sink; (void)ctx;
}

int main(void) {
    double med;
    fill_buf_a = malloc(FILL_N * 4);
    fill_buf_b = malloc(FILL_N * 4);
    sumsq_a = malloc(SUMSQ_N * 8);
    bytes_buf = malloc(BYTES_N);
    if (!fill_buf_a || !fill_buf_b || !sumsq_a || !bytes_buf) return 2;
    for (int i = 0; i < 4096; i++) span_tex[i] = (uint32_t)(i * 2654435761u) >> 8;
    for (int64_t i = 0; i < SUMSQ_N; i++) sumsq_a[i] = i + 1;
    for (int64_t i = 0; i < BYTES_N; i++)
        bytes_buf[i] = (uint8_t)(((uint32_t)i * 1103515245u + 12345u) >> 16);

    /* fill32 */
    ref_fill32(fill_buf_a, FILL_N, 0x12345678u);
    fill32(fill_buf_b, FILL_N, 0x12345678);
    if (memcmp(fill_buf_a, fill_buf_b, FILL_N * 4)) die("fill32", "output mismatch");
    {
        unsigned long long cs = sum_u32(fill_buf_a, FILL_N);
        double bc = bench(run_fill_c, NULL, 20, &med), mc = med;
        double bk = bench(run_fill_k, NULL, 20, &med), mk = med;
        emit("fill32", IMPL_NAME, bc, mc, cs);
        emit("fill32", "krell", bk, mk, cs);
    }
    /* span */
    ref_span(span_a, span_tex, SPAN_W, 3 << 16, 5 << 16, 70000, -30000, 200);
    span(span_b, span_tex, SPAN_W, 3 << 16, 5 << 16, 70000, -30000, 200);
    if (memcmp(span_a, span_b, SPAN_W * 4)) die("span", "output mismatch");
    {
        unsigned long long cs = sum_u32(span_a, SPAN_W);
        double bc = bench(run_span_c, NULL, 200, &med), mc = med;
        double bk = bench(run_span_k, NULL, 200, &med), mk = med;
        emit("span", IMPL_NAME, bc, mc, cs);
        emit("span", "krell", bk, mk, cs);
    }
    /* sumsq */
    {
        int64_t rc = ref_sumsq(sumsq_a, SUMSQ_N), rk = sumsq(sumsq_a, SUMSQ_N);
        if (rc != rk) die("sumsq", "value mismatch");
        { double bc = bench(run_sumsq_c, NULL, 20, &med), mc = med;
          double bk = bench(run_sumsq_k, NULL, 20, &med), mk = med;
          emit("sumsq", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("sumsq", "krell", bk, mk, (unsigned long long)rk); }
    }
    /* fib */
    {
        int64_t rc = ref_fib(32), rk = fib(32);
        if (rc != rk) die("fib", "value mismatch");
        { double bc = bench(run_fib_c, NULL, 15, &med), mc = med;
          double bk = bench(run_fib_k, NULL, 15, &med), mk = med;
          emit("fib", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("fib", "krell", bk, mk, (unsigned long long)rk); }
    }
    /* histo */
    memset(hist_a, 0, sizeof hist_a);
    memset(hist_b, 0, sizeof hist_b);
    ref_histo(bytes_buf, BYTES_N, hist_a);
    histo(bytes_buf, BYTES_N, hist_b);
    if (memcmp(hist_a, hist_b, sizeof hist_a)) die("histo", "output mismatch");
    {
        unsigned long long cs = hist_checksum(hist_a);
        double bc = bench(run_histo_c, NULL, 5, &med), mc = med;
        double bk = bench(run_histo_k, NULL, 5, &med), mk = med;
        emit("histo", IMPL_NAME, bc, mc, cs);
        emit("histo", "krell", bk, mk, cs);
    }
    /* fnv1a */
    {
        uint64_t rc = ref_fnv1a(bytes_buf, BYTES_N);
        int64_t rk = fnv1a(bytes_buf, BYTES_N);
        if (rc != (uint64_t)rk) die("fnv1a", "value mismatch");
        { double bc = bench(run_fnv_c, NULL, 5, &med), mc = med;
          double bk = bench(run_fnv_k, NULL, 5, &med), mk = med;
          emit("fnv1a", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("fnv1a", "krell", bk, mk, (unsigned long long)rk); }
    }
    return 0;
}
