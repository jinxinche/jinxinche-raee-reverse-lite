/*
 * Synthetic development sample for RAEE Reverse Lite.
 * This is not the frozen real target (zlib 1.4 / minigzip).
 *
 * Reads stdin, up to 4096 bytes, and prints:
 *   count=<nbytes> sum=<sum of bytes mod 65521>
 * --fail exits 3 after printing. --spin does not return.
 * Any other argument exits 2.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint32_t checksum(const unsigned char *data, size_t length, uint32_t *count)
{
    uint32_t sum = 0;
    size_t index;
    for (index = 0; index < length; index++) {
        sum = (sum + data[index]) % 65521u;
    }
    *count = (uint32_t)length;
    return sum;
}

int main(int argc, char **argv)
{
    unsigned char buffer[4096];
    size_t length = 0;
    uint32_t count = 0;
    int fail = 0;
    int index;

    for (index = 1; index < argc; index++) {
        if (strcmp(argv[index], "--fail") == 0) {
            fail = 1;
        } else if (strcmp(argv[index], "--spin") == 0) {
            for (;;) {
            }
        } else {
            fprintf(stderr, "unknown argument\n");
            return 2;
        }
    }

    while (length < sizeof(buffer)) {
        size_t got = fread(buffer + length, 1, sizeof(buffer) - length, stdin);
        if (got == 0) {
            break;
        }
        length += got;
    }
    if (length == sizeof(buffer)) {
        int extra = fgetc(stdin);
        if (extra != EOF) {
            fprintf(stderr, "input too large\n");
            return 2;
        }
    }

    printf("count=%u sum=%u\n", count, checksum(buffer, length, &count));
    if (fail) {
        return 3;
    }
    return 0;
}
