/* KRELLPROOF C reference implementations.
 * These define the semantics every other implementation is checked
 * against: identical inputs must produce identical outputs. */
#include <stdint.h>
#include <stddef.h>

void ref_fill32(uint32_t *dst, int64_t n, uint32_t val) {
    for (int64_t i = 0; i < n; i++) dst[i] = val;
}

void ref_span(uint32_t *dst, const uint32_t *tex, int64_t w,
              int32_t u0, int32_t v0, int32_t du, int32_t dv, int32_t light) {
    int32_t u = u0, v = v0;
    for (int64_t x = 0; x < w; x++) {
        int tx = (u >> 16) & 63, ty = (v >> 16) & 63;
        uint32_t px = tex[ty * 64 + tx];
        uint32_t r = (((px >> 16) & 0xff) * (uint32_t)light) >> 8;
        uint32_t g = (((px >> 8) & 0xff) * (uint32_t)light) >> 8;
        uint32_t b = ((px & 0xff) * (uint32_t)light) >> 8;
        dst[x] = (r << 16) | (g << 8) | b;
        u += du; v += dv;
    }
}

int64_t ref_sumsq(const int64_t *a, int64_t n) {
    int64_t s = 0;
    for (int64_t i = 0; i < n; i++) s += a[i] * a[i];
    return s;
}

int64_t ref_fib(int64_t n) {
    return n < 2 ? n : ref_fib(n - 1) + ref_fib(n - 2);
}

void ref_histo(const uint8_t *buf, int64_t n, int64_t *hist) {
    for (int64_t i = 0; i < n; i++) hist[buf[i]]++;
}

uint64_t ref_fnv1a(const uint8_t *buf, int64_t n) {
    uint64_t h = 14695981039346656037ULL;
    for (int64_t i = 0; i < n; i++) { h ^= buf[i]; h *= 1099511628211ULL; }
    return h;
}

int64_t ref_dot(const int64_t *a, const int64_t *b, int64_t n) {
    int64_t s = 0;
    for (int64_t i = 0; i < n; i++) s += a[i] * b[i];
    return s;
}

void ref_saxpy(int32_t *y, const int32_t *x, int64_t n, int32_t a) {
    for (int64_t i = 0; i < n; i++) y[i] = a * x[i] + y[i];
}

void ref_copy(uint32_t *dst, const uint32_t *src, int64_t n) {
    for (int64_t i = 0; i < n; i++) dst[i] = src[i];
}

uint64_t ref_bytesum(const uint8_t *buf, int64_t n) {
    uint64_t s = 0;
    for (int64_t i = 0; i < n; i++) s += buf[i];
    return s;
}

int64_t ref_parse(const uint8_t *buf, int64_t n) {
    int64_t s = 0, cur = 0;
    int inn = 0;
    for (int64_t i = 0; i < n; i++) {
        uint8_t c = buf[i];
        if (c >= '0' && c <= '9') { cur = cur * 10 + (c - '0'); inn = 1; }
        else if (inn) { s += cur; cur = 0; inn = 0; }
    }
    if (inn) s += cur;
    return s;
}

void ref_mix(uint64_t *dst, const uint64_t *src, int64_t n) {
    for (int64_t i = 0; i < n; i++) {
        uint64_t z = src[i] + 0x9E3779B97F4A7C15ULL;
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        dst[i] = z ^ (z >> 31);
    }
}
