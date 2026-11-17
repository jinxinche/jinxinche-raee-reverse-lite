/* Single-thread CRC-32 (ISO-HDLC) using PCLMULQDQ.
 *
 * The fold below is adapted from Chromium third_party/zlib/crc32_simd.c
 * (crc32_sse42_simd_). Copyright 2017 The Chromium Authors.
 * Use and redistribution follow the BSD license in the Chromium repository:
 * https://chromium.googlesource.com/chromium/src/+/refs/heads/main/LICENSE
 * This file is altered: it is not the original Chromium source, and it is
 * not zlib's crc32.c. It does not use CFLAGS=-O3 -flto. That flag pair is
 * the closed missed goal in docs/phase4/GOAL.md.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *   * Redistributions of source code must retain the above copyright notice,
 *     this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in the
 *     documentation and/or other materials provided with the distribution.
 *   * Neither the name of Google LLC nor the names of its contributors may
 *     be used to endorse or promote products derived from this software
 *     without specific prior written permission.
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#include <stddef.h>
#include <stdint.h>
#include <emmintrin.h>
#include <smmintrin.h>
#include <wmmintrin.h>

#if defined(__GNUC__) || defined(__clang__)
__attribute__((target("sse4.2,pclmul")))
#endif
uint32_t crc32_sse42_simd_(  /* SSE4.2+PCLMUL */
    const unsigned char *buf,
    size_t len,
    uint32_t crc)
{
    /*
     * Definitions of the bit-reflected domain constants k1,k2,k3, etc and
     * the CRC32+Barrett polynomials given at the end of the paper.
     */
    static const uint64_t __attribute__((aligned(16))) k1k2[] = { 0x0154442bd4, 0x01c6e41596 };
    static const uint64_t __attribute__((aligned(16))) k3k4[] = { 0x01751997d0, 0x00ccaa009e };
    static const uint64_t __attribute__((aligned(16))) k5k0[] = { 0x0163cd6124, 0x0000000000 };
    static const uint64_t __attribute__((aligned(16))) poly[] = { 0x01db710641, 0x01f7011641 };

    __m128i x0, x1, x2, x3, x4, x5, x6, x7, x8, y5, y6, y7, y8;

    /*
     * There's at least one block of 64.
     */
    x1 = _mm_loadu_si128((__m128i *)(buf + 0x00));
    x2 = _mm_loadu_si128((__m128i *)(buf + 0x10));
    x3 = _mm_loadu_si128((__m128i *)(buf + 0x20));
    x4 = _mm_loadu_si128((__m128i *)(buf + 0x30));

    x1 = _mm_xor_si128(x1, _mm_cvtsi32_si128(crc));

    x0 = _mm_load_si128((__m128i *)k1k2);

    buf += 64;
    len -= 64;

    /*
     * Parallel fold blocks of 64, if any.
     */
    while (len >= 64)
    {
        x5 = _mm_clmulepi64_si128(x1, x0, 0x00);
        x6 = _mm_clmulepi64_si128(x2, x0, 0x00);
        x7 = _mm_clmulepi64_si128(x3, x0, 0x00);
        x8 = _mm_clmulepi64_si128(x4, x0, 0x00);

        x1 = _mm_clmulepi64_si128(x1, x0, 0x11);
        x2 = _mm_clmulepi64_si128(x2, x0, 0x11);
        x3 = _mm_clmulepi64_si128(x3, x0, 0x11);
        x4 = _mm_clmulepi64_si128(x4, x0, 0x11);

        y5 = _mm_loadu_si128((__m128i *)(buf + 0x00));
        y6 = _mm_loadu_si128((__m128i *)(buf + 0x10));
        y7 = _mm_loadu_si128((__m128i *)(buf + 0x20));
        y8 = _mm_loadu_si128((__m128i *)(buf + 0x30));

        x1 = _mm_xor_si128(x1, x5);
        x2 = _mm_xor_si128(x2, x6);
        x3 = _mm_xor_si128(x3, x7);
        x4 = _mm_xor_si128(x4, x8);

        x1 = _mm_xor_si128(x1, y5);
        x2 = _mm_xor_si128(x2, y6);
        x3 = _mm_xor_si128(x3, y7);
        x4 = _mm_xor_si128(x4, y8);

        buf += 64;
        len -= 64;
    }

    /*
     * Fold into 128-bits.
     */
    x0 = _mm_load_si128((__m128i *)k3k4);

    x5 = _mm_clmulepi64_si128(x1, x0, 0x00);
    x1 = _mm_clmulepi64_si128(x1, x0, 0x11);
    x1 = _mm_xor_si128(x1, x2);
    x1 = _mm_xor_si128(x1, x5);

    x5 = _mm_clmulepi64_si128(x1, x0, 0x00);
    x1 = _mm_clmulepi64_si128(x1, x0, 0x11);
    x1 = _mm_xor_si128(x1, x3);
    x1 = _mm_xor_si128(x1, x5);

    x5 = _mm_clmulepi64_si128(x1, x0, 0x00);
    x1 = _mm_clmulepi64_si128(x1, x0, 0x11);
    x1 = _mm_xor_si128(x1, x4);
    x1 = _mm_xor_si128(x1, x5);

    /*
     * Single fold blocks of 16, if any.
     */
    while (len >= 16)
    {
        x2 = _mm_loadu_si128((__m128i *)buf);

        x5 = _mm_clmulepi64_si128(x1, x0, 0x00);
        x1 = _mm_clmulepi64_si128(x1, x0, 0x11);
        x1 = _mm_xor_si128(x1, x2);
        x1 = _mm_xor_si128(x1, x5);

        buf += 16;
        len -= 16;
    }

    /*
     * Fold 128-bits to 64-bits.
     */
    x2 = _mm_clmulepi64_si128(x1, x0, 0x10);
    x3 = _mm_setr_epi32(~0, 0, ~0, 0);
    x1 = _mm_srli_si128(x1, 8);
    x1 = _mm_xor_si128(x1, x2);

    x0 = _mm_loadl_epi64((__m128i*)k5k0);

    x2 = _mm_srli_si128(x1, 4);
    x1 = _mm_and_si128(x1, x3);
    x1 = _mm_clmulepi64_si128(x1, x0, 0x00);
    x1 = _mm_xor_si128(x1, x2);

    /*
     * Barret reduce to 32-bits.
     */
    x0 = _mm_load_si128((__m128i*)poly);

    x2 = _mm_and_si128(x1, x3);
    x2 = _mm_clmulepi64_si128(x2, x0, 0x10);
    x2 = _mm_and_si128(x2, x3);
    x2 = _mm_clmulepi64_si128(x2, x0, 0x00);
    x1 = _mm_xor_si128(x1, x2);

    /*
     * Return the crc32.
     */
    return _mm_extract_epi32(x1, 1);
}



#include "zlib.h"
#include <cpuid.h>

static int pclmul_available(void) {
    static int cached = -1;
    unsigned int a, b, c, d;
    if (cached >= 0) return cached;
    if (!__get_cpuid(1, &a, &b, &c, &d)) {
        cached = 0;
        return 0;
    }
    cached = ((c & bit_PCLMUL) != 0 && (c & bit_SSE4_1) != 0) ? 1 : 0;
    return cached;
}

/* Return 1 when *out is the CRC. Buffers under 64 bytes, or CPUs without
 * PCLMULQDQ and SSE4.1, return 0 so crc32_z keeps the stock path. The tail
 * is shorter than 16 bytes, so the stock call does not re-enter this path.
 */
int crc32_z_pclmul_try(uLong crc, const Bytef *buf, z_size_t len, uLong *out) {
    z_size_t aligned;
    uint32_t folded;
    uLong partial;
    if (buf == Z_NULL || out == Z_NULL) return 0;
    if (!pclmul_available() || len < 64) return 0;
    aligned = len & ~(z_size_t)15;
    if (aligned < 64) return 0;
    folded = crc32_sse42_simd_((const unsigned char *)buf, (size_t)aligned,
                               (uint32_t)((~crc) & 0xffffffffu));
    partial = ((uLong)folded) ^ ((uLong)0xffffffffu);
    if (aligned == len) {
        *out = partial;
        return 1;
    }
    *out = crc32_z(partial, buf + aligned, len - aligned);
    return 1;
}
