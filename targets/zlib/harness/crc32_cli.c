/* Harness around zlib's crc32. This file is not part of zlib. */
#include <stdio.h>
#include <zlib.h>

int main(void) {
    unsigned char buffer[1 << 20];
    size_t length = fread(buffer, 1, sizeof buffer, stdin);
    if (length == sizeof buffer) {
        int extra = fgetc(stdin);
        if (extra != EOF) {
            fprintf(stderr, "input too large\n");
            return 2;
        }
    }
    unsigned long value = crc32(0L, buffer, (uInt)length);
    printf("%08lx\n", value);
    return 0;
}
