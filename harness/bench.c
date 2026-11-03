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
#ifndef KRELL_IMPL_NAME
#define KRELL_IMPL_NAME "krell"
#endif

/* C references (kernels/refs.c) */
void ref_fill32(uint32_t *, int64_t, uint32_t);
void ref_span(uint32_t *, const uint32_t *, int64_t, int32_t, int32_t, int32_t, int32_t, int32_t);
int64_t ref_sumsq(const int64_t *, int64_t);
int64_t ref_fib(int64_t);
void ref_histo(const uint8_t *, int64_t, int64_t *);
uint64_t ref_fnv1a(const uint8_t *, int64_t);
int64_t ref_dot(const int64_t *, const int64_t *, int64_t);
void ref_saxpy(int32_t *, const int32_t *, int64_t, int32_t);
void ref_copy(uint32_t *, const uint32_t *, int64_t);
uint64_t ref_bytesum(const uint8_t *, int64_t);
int64_t ref_parse(const uint8_t *, int64_t);
void ref_mix(uint64_t *, const uint64_t *, int64_t);

/* Krell-compiled kernels */
void fill32(void *, int64_t, int32_t);
void span(void *, const void *, int64_t, int32_t, int32_t, int32_t, int32_t, int32_t);
int64_t sumsq(const void *, int64_t);
int64_t fib(int64_t);
void histo(const void *, int64_t, void *);
int64_t fnv1a(const void *, int64_t);
int64_t dot(const void *, const void *, int64_t);
void saxpy(void *, const void *, int64_t, int32_t);
void copy(void *, const void *, int64_t);
int64_t bytesum(const void *, int64_t);
int64_t parse(const void *, int64_t);
void mix(void *, const void *, int64_t);

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
#ifdef KRELL_ONLY
    if (strcmp(impl, IMPL_NAME) == 0) return;
#endif
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

/* ---------------- WP5 kernels ---------------- */
#define STREAM_N (1 << 20)
static int64_t *dot_a, *dot_b;
static int32_t *sax_x, *sax_ya, *sax_yb;
static uint32_t *copy_src, *copy_da, *copy_db;
static uint8_t *parse_buf;
static uint64_t *mix_src, *mix_da, *mix_db;
static void run_dot_c(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = ref_dot(dot_a, dot_b, STREAM_N);
    (void)sink; (void)ctx;
}
static void run_dot_k(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = dot(dot_a, dot_b, STREAM_N);
    (void)sink; (void)ctx;
}
static void run_saxpy_c(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) ref_saxpy(sax_ya, sax_x, STREAM_N, 3);
}
static void run_saxpy_k(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) saxpy(sax_yb, sax_x, STREAM_N, 3);
}
static void run_copy_c(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) ref_copy(copy_da, copy_src, STREAM_N);
}
static void run_copy_k(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) copy(copy_db, copy_src, STREAM_N);
}
static void run_bytesum_c(void *ctx, int reps) {
    volatile uint64_t sink;
    for (int i = 0; i < reps; i++) sink = ref_bytesum(bytes_buf, BYTES_N);
    (void)sink; (void)ctx;
}
static void run_bytesum_k(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = bytesum(bytes_buf, BYTES_N);
    (void)sink; (void)ctx;
}
#define PARSE_N (1 << 20)
static void run_parse_c(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = ref_parse(parse_buf, PARSE_N);
    (void)sink; (void)ctx;
}
static void run_parse_k(void *ctx, int reps) {
    volatile int64_t sink;
    for (int i = 0; i < reps; i++) sink = parse(parse_buf, PARSE_N);
    (void)sink; (void)ctx;
}
static void run_mix_c(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) ref_mix(mix_da, mix_src, STREAM_N);
}
static void run_mix_k(void *ctx, int reps) {
    (void)ctx;
    for (int i = 0; i < reps; i++) mix(mix_db, mix_src, STREAM_N);
}
static unsigned long long sum_u64(const uint64_t *b, int64_t n) {
    unsigned long long s = 0;
    for (int64_t i = 0; i < n; i++) s += (unsigned long long)b[i];
    return s;
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
    dot_a = malloc(STREAM_N * 8);
    dot_b = malloc(STREAM_N * 8);
    sax_x = malloc(STREAM_N * 4);
    sax_ya = malloc(STREAM_N * 4);
    sax_yb = malloc(STREAM_N * 4);
    copy_src = malloc(STREAM_N * 4);
    copy_da = malloc(STREAM_N * 4);
    copy_db = malloc(STREAM_N * 4);
    parse_buf = malloc(PARSE_N);
    mix_src = malloc(STREAM_N * 8);
    mix_da = malloc(STREAM_N * 8);
    mix_db = malloc(STREAM_N * 8);
    if (!dot_a || !dot_b || !sax_x || !sax_ya || !sax_yb || !copy_src ||
        !copy_da || !copy_db || !parse_buf || !mix_src || !mix_da || !mix_db)
        return 2;
    for (int64_t i = 0; i < STREAM_N; i++) {
        dot_a[i] = i + 1;
        dot_b[i] = (i % 7) + 3;
        sax_x[i] = (int32_t)(i + 1);
        sax_ya[i] = sax_yb[i] = (int32_t)((i % 5) + 1);
        copy_src[i] = (uint32_t)((uint32_t)i * 2654435761u) >> 8;
        mix_src[i] = (uint64_t)(i + 1);
    }
    for (int64_t g = 0; g < PARSE_N / 8; g++)
        memcpy(parse_buf + g * 8, "1234567 ", 8);

    /* fill32 */
    ref_fill32(fill_buf_a, FILL_N, 0x12345678u);
    fill32(fill_buf_b, FILL_N, 0x12345678);
    if (memcmp(fill_buf_a, fill_buf_b, FILL_N * 4)) die("fill32", "output mismatch");
    {
        unsigned long long cs = sum_u32(fill_buf_a, FILL_N);
        double bc = bench(run_fill_c, NULL, 20, &med), mc = med;
        double bk = bench(run_fill_k, NULL, 20, &med), mk = med;
        emit("fill32", IMPL_NAME, bc, mc, cs);
        emit("fill32", KRELL_IMPL_NAME, bk, mk, cs);
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
        emit("span", KRELL_IMPL_NAME, bk, mk, cs);
    }
    /* sumsq */
    {
        int64_t rc = ref_sumsq(sumsq_a, SUMSQ_N), rk = sumsq(sumsq_a, SUMSQ_N);
        if (rc != rk) die("sumsq", "value mismatch");
        { double bc = bench(run_sumsq_c, NULL, 20, &med), mc = med;
          double bk = bench(run_sumsq_k, NULL, 20, &med), mk = med;
          emit("sumsq", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("sumsq", KRELL_IMPL_NAME, bk, mk, (unsigned long long)rk); }
    }
    /* fib */
    {
        int64_t rc = ref_fib(32), rk = fib(32);
        if (rc != rk) die("fib", "value mismatch");
        { double bc = bench(run_fib_c, NULL, 15, &med), mc = med;
          double bk = bench(run_fib_k, NULL, 15, &med), mk = med;
          emit("fib", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("fib", KRELL_IMPL_NAME, bk, mk, (unsigned long long)rk); }
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
        emit("histo", KRELL_IMPL_NAME, bk, mk, cs);
    }
    /* fnv1a */
    {
        uint64_t rc = ref_fnv1a(bytes_buf, BYTES_N);
        int64_t rk = fnv1a(bytes_buf, BYTES_N);
        if (rc != (uint64_t)rk) die("fnv1a", "value mismatch");
        { double bc = bench(run_fnv_c, NULL, 5, &med), mc = med;
          double bk = bench(run_fnv_k, NULL, 5, &med), mk = med;
          emit("fnv1a", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("fnv1a", KRELL_IMPL_NAME, bk, mk, (unsigned long long)rk); }
    }
    /* dot */
    {
        int64_t rc = ref_dot(dot_a, dot_b, STREAM_N), rk = dot(dot_a, dot_b, STREAM_N);
        if (rc != rk) die("dot", "value mismatch");
        { double bc = bench(run_dot_c, NULL, 20, &med), mc = med;
          double bk = bench(run_dot_k, NULL, 20, &med), mk = med;
          emit("dot", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("dot", KRELL_IMPL_NAME, bk, mk, (unsigned long long)rk); }
    }
    /* saxpy: checksum is the output after exactly one application */
    ref_saxpy(sax_ya, sax_x, STREAM_N, 3);
    saxpy(sax_yb, sax_x, STREAM_N, 3);
    if (memcmp(sax_ya, sax_yb, STREAM_N * 4)) die("saxpy", "output mismatch");
    {
        unsigned long long cs = sum_u32((const uint32_t *)sax_ya, STREAM_N);
        double bc = bench(run_saxpy_c, NULL, 20, &med), mc = med;
        double bk = bench(run_saxpy_k, NULL, 20, &med), mk = med;
        emit("saxpy", IMPL_NAME, bc, mc, cs);
        emit("saxpy", KRELL_IMPL_NAME, bk, mk, cs);
    }
    /* copy */
    ref_copy(copy_da, copy_src, STREAM_N);
    copy(copy_db, copy_src, STREAM_N);
    if (memcmp(copy_da, copy_db, STREAM_N * 4)) die("copy", "output mismatch");
    {
        unsigned long long cs = sum_u32(copy_src, STREAM_N);
        double bc = bench(run_copy_c, NULL, 20, &med), mc = med;
        double bk = bench(run_copy_k, NULL, 20, &med), mk = med;
        emit("copy", IMPL_NAME, bc, mc, cs);
        emit("copy", KRELL_IMPL_NAME, bk, mk, cs);
    }
    /* bytesum */
    {
        uint64_t rc = ref_bytesum(bytes_buf, BYTES_N);
        int64_t rk = bytesum(bytes_buf, BYTES_N);
        if (rc != (uint64_t)rk) die("bytesum", "value mismatch");
        { double bc = bench(run_bytesum_c, NULL, 5, &med), mc = med;
          double bk = bench(run_bytesum_k, NULL, 5, &med), mk = med;
          emit("bytesum", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("bytesum", KRELL_IMPL_NAME, bk, mk, (unsigned long long)rk); }
    }
    /* parse */
    {
        int64_t rc = ref_parse(parse_buf, PARSE_N), rk = parse(parse_buf, PARSE_N);
        if (rc != rk) die("parse", "value mismatch");
        { double bc = bench(run_parse_c, NULL, 10, &med), mc = med;
          double bk = bench(run_parse_k, NULL, 10, &med), mk = med;
          emit("parse", IMPL_NAME, bc, mc, (unsigned long long)rc);
          emit("parse", KRELL_IMPL_NAME, bk, mk, (unsigned long long)rk); }
    }
    /* mix */
    ref_mix(mix_da, mix_src, STREAM_N);
    mix(mix_db, mix_src, STREAM_N);
    if (memcmp(mix_da, mix_db, STREAM_N * 8)) die("mix", "output mismatch");
    {
        unsigned long long cs = sum_u64(mix_da, STREAM_N);
        double bc = bench(run_mix_c, NULL, 20, &med), mc = med;
        double bk = bench(run_mix_k, NULL, 20, &med), mk = med;
        emit("mix", IMPL_NAME, bc, mc, cs);
        emit("mix", KRELL_IMPL_NAME, bk, mk, cs);
    }
    return 0;
}
