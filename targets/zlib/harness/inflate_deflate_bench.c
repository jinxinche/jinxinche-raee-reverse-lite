/* Clock one gzip deflate and one gzip inflate of the 4 MiB buffer.
 * Process start is outside the samples.
 * The buffer formula and the call boundaries are frozen in
 * docs/phase4/GOAL_MINIGZIP_ATTEMPT4.json.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <zlib.h>

enum { PAYLOAD = 4 * 1024 * 1024, SAMPLES = 22, SPIN_LIMIT = 8 };

static void fill(unsigned char *buffer, size_t length) {
    size_t index;
    for (index = 0; index < length; index++)
        buffer[index] = (unsigned char)(index % 251u);
}

static double seconds_between(struct timespec start, struct timespec stop) {
    return (double)(stop.tv_sec - start.tv_sec) +
           (double)(stop.tv_nsec - start.tv_nsec) / 1e9;
}

static int compress_once(
    unsigned char *plain,
    unsigned char *out,
    uLong capacity,
    uLong *length,
    double *elapsed
) {
    z_stream stream;
    struct timespec start, stop;
    int rc;
    int spins = 0;
    memset(&stream, 0, sizeof stream);
    clock_gettime(CLOCK_MONOTONIC, &start);
    rc = deflateInit2(
        &stream,
        Z_DEFAULT_COMPRESSION,
        Z_DEFLATED,
        15 + 16,
        8,
        Z_DEFAULT_STRATEGY
    );
    if (rc != Z_OK) return 1;
    stream.next_in = plain;
    stream.avail_in = (uInt)PAYLOAD;
    stream.next_out = out;
    stream.avail_out = (uInt)capacity;
    do {
        rc = deflate(&stream, Z_FINISH);
        spins++;
    } while (rc == Z_OK && spins < SPIN_LIMIT);
    *length = stream.total_out;
    deflateEnd(&stream);
    clock_gettime(CLOCK_MONOTONIC, &stop);
    *elapsed = seconds_between(start, stop);
    if (rc != Z_STREAM_END || *length == 0 || *length > capacity) return 1;
    return 0;
}

static int decompress_once(
    unsigned char *gzip,
    uLong gzip_length,
    unsigned char *out,
    double *elapsed
) {
    z_stream stream;
    struct timespec start, stop;
    int rc;
    int spins = 0;
    memset(&stream, 0, sizeof stream);
    clock_gettime(CLOCK_MONOTONIC, &start);
    rc = inflateInit2(&stream, 15 + 16);
    if (rc != Z_OK) return 1;
    stream.next_in = gzip;
    stream.avail_in = (uInt)gzip_length;
    stream.next_out = out;
    stream.avail_out = (uInt)PAYLOAD;
    do {
        rc = inflate(&stream, Z_NO_FLUSH);
        spins++;
    } while (rc == Z_OK && spins < SPIN_LIMIT);
    inflateEnd(&stream);
    clock_gettime(CLOCK_MONOTONIC, &stop);
    *elapsed = seconds_between(start, stop);
    if (rc != Z_STREAM_END || stream.total_out != PAYLOAD) return 1;
    return 0;
}

static int write_gzip(const unsigned char *gzip, uLong length) {
    FILE *file = fopen("attempt4_gzip.bin", "wb");
    if (file == NULL) return 1;
    if (fwrite(gzip, 1, (size_t)length, file) != (size_t)length) {
        fclose(file);
        return 1;
    }
    if (fclose(file) != 0) return 1;
    return 0;
}

int main(void) {
    unsigned char *plain;
    unsigned char *reference;
    unsigned char *got;
    unsigned char *back;
    z_stream bound_stream;
    uLong bound;
    uLong reference_length = 0;
    double compress_samples[SAMPLES];
    double decompress_samples[SAMPLES];
    int index;
    plain = malloc(PAYLOAD);
    if (plain == NULL) return 1;
    fill(plain, PAYLOAD);
    memset(&bound_stream, 0, sizeof bound_stream);
    if (deflateInit2(
            &bound_stream,
            Z_DEFAULT_COMPRESSION,
            Z_DEFLATED,
            15 + 16,
            8,
            Z_DEFAULT_STRATEGY) != Z_OK) {
        free(plain);
        return 1;
    }
    bound = deflateBound(&bound_stream, PAYLOAD);
    deflateEnd(&bound_stream);
    if (bound < 18 || bound > 0xffffffffu) {
        free(plain);
        return 1;
    }
    reference = malloc((size_t)bound);
    got = malloc((size_t)bound);
    back = malloc(PAYLOAD);
    if (reference == NULL || got == NULL || back == NULL) {
        free(plain);
        free(reference);
        free(got);
        free(back);
        return 1;
    }
    for (index = 0; index < SAMPLES; index++) {
        uLong length = 0;
        if (compress_once(plain, got, bound, &length, &compress_samples[index]) != 0) {
            free(plain);
            free(reference);
            free(got);
            free(back);
            return 2;
        }
        if (index == 0) {
            memcpy(reference, got, (size_t)length);
            reference_length = length;
        } else if (length != reference_length ||
                   memcmp(reference, got, (size_t)length) != 0) {
            free(plain);
            free(reference);
            free(got);
            free(back);
            return 3;
        }
    }
    if (reference_length < 10 ||
        reference[0] != 0x1f ||
        reference[1] != 0x8b ||
        reference[2] != 8 ||
        reference[4] != 0 ||
        reference[5] != 0 ||
        reference[6] != 0 ||
        reference[7] != 0) {
        free(plain);
        free(reference);
        free(got);
        free(back);
        return 4;
    }
    for (index = 0; index < SAMPLES; index++) {
        if (decompress_once(reference, reference_length, back, &decompress_samples[index]) != 0 ||
            memcmp(back, plain, PAYLOAD) != 0) {
            free(plain);
            free(reference);
            free(got);
            free(back);
            return 5;
        }
    }
    if (write_gzip(reference, reference_length) != 0) {
        free(plain);
        free(reference);
        free(got);
        free(back);
        return 6;
    }
    printf("round_trip ok\n");
    printf("gzip_magic 1f8b\n");
    printf("gzip_mtime 00000000\n");
    printf("crc32_abc %08lx\n", crc32(0L, (const Bytef *)"abc", 3));
    printf("payload_crc %08lx\n", crc32(0L, plain, (uInt)PAYLOAD));
    printf("gzip_bytes %lu\n", reference_length);
    for (index = 0; index < SAMPLES; index++)
        printf("compress %.9f\n", compress_samples[index]);
    for (index = 0; index < SAMPLES; index++)
        printf("decompress %.9f\n", decompress_samples[index]);
    free(plain);
    free(reference);
    free(got);
    free(back);
    return 0;
}
