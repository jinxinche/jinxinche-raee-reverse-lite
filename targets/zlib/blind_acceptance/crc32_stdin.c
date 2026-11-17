/* Stream stdin through the linked libz crc32(). Print eight lowercase hex digits.

   This is a checker harness. It is not a zlib candidate and it does not
   change minigzip. The frozen speed bench stops at 2 MiB, which is smaller
   than enwik8, so the acceptance check cannot use that bench.
*/
#include <stdio.h>
#include <zlib.h>

int main(void) {
    unsigned char buffer[65536];
    uLong crc = crc32(0L, Z_NULL, 0);
    size_t got;

    while ((got = fread(buffer, 1, sizeof buffer, stdin)) > 0) {
        crc = crc32(crc, buffer, (uInt)got);
    }
    if (ferror(stdin)) {
        return 1;
    }
    printf("%08lx\n", crc);
    return 0;
}
