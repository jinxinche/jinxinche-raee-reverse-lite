/* Clock one base64_encode call. This is the measurement harness, not the candidate. */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "libbase64.h"

int main(void) {
    const size_t length = 8u * 1024u * 1024u;
    char *input = malloc(length);
    char *output = malloc((length / 3u + 2u) * 4u);
    size_t encoded = 0;
    struct timespec start;
    struct timespec stop;
    long long nanoseconds;
    FILE *sink;

    if (input == NULL || output == NULL) {
        return 2;
    }
    for (size_t index = 0; index < length; index++) {
        input[index] = (char)(index % 251u);
    }
    clock_gettime(CLOCK_MONOTONIC, &start);
    base64_encode(input, length, output, &encoded, 0);
    clock_gettime(CLOCK_MONOTONIC, &stop);
    nanoseconds = (long long)(stop.tv_sec - start.tv_sec) * 1000000000LL
        + (long long)(stop.tv_nsec - start.tv_nsec);
    sink = fopen("encoded.bin", "wb");
    if (sink == NULL) {
        return 3;
    }
    if (fwrite(output, 1, encoded, sink) != encoded) {
        return 4;
    }
    fclose(sink);
    printf("ns=%lld outlen=%zu\n", nanoseconds, encoded);
    return 0;
}
