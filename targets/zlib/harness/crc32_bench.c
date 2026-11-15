/* Clock crc32() only. Process start is outside the samples.
 * The 16 MiB formula is the one frozen in docs/phase4/GOAL_CRC32.json.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <zlib.h>

enum { PAYLOAD = 16 * 1024 * 1024, RUNS = 22 };

static void fill(unsigned char *buffer, size_t length) {
    size_t index;
    for (index = 0; index < length; index++) {
        buffer[index] = (unsigned char)((index * 17u + 3u) & 0xffu);
    }
}

static int speed(void) {
    unsigned char *buffer = malloc(PAYLOAD);
    struct timespec start, stop;
    unsigned long expected, value;
    int index;
    if (buffer == NULL) return 1;
    fill(buffer, PAYLOAD);
    expected = crc32(0L, buffer, (uInt)PAYLOAD);
    printf("payload_crc %08lx\n", expected);
    printf("check123456789 %08lx\n", crc32(0L, (const Bytef *)"123456789", 9));
    for (index = 0; index < RUNS; index++) {
        clock_gettime(CLOCK_MONOTONIC, &start);
        value = crc32(0L, buffer, (uInt)PAYLOAD);
        clock_gettime(CLOCK_MONOTONIC, &stop);
        if (value != expected) {
            free(buffer);
            return 2;
        }
        printf(
            "sample %.9f\n",
            (double)(stop.tv_sec - start.tv_sec) + (double)(stop.tv_nsec - start.tv_nsec) / 1e9
        );
    }
    free(buffer);
    return 0;
}

static int crc_stdin(void) {
    unsigned char *buffer = malloc(2 * 1024 * 1024);
    size_t length = 0;
    unsigned long value;
    if (buffer == NULL) return 1;
    while (length < 2 * 1024 * 1024) {
        size_t got = fread(buffer + length, 1, (2 * 1024 * 1024) - length, stdin);
        if (got == 0) break;
        length += got;
    }
    if (length == 2 * 1024 * 1024) {
        int extra = fgetc(stdin);
        if (extra != EOF) {
            fprintf(stderr, "input too large\n");
            free(buffer);
            return 2;
        }
    }
    value = crc32(0L, buffer, (uInt)length);
    printf("%08lx\n", value);
    free(buffer);
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "crc") == 0) return crc_stdin();
    return speed();
}
