/* Clock one luaL_loadbuffer call. This is the measurement harness, not the candidate. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "lua.h"
#include "lauxlib.h"

int main(int argc, char **argv) {
    int repetitions;
    const char *mode;
    char *buffer;
    size_t length;
    lua_State *state;
    struct timespec start;
    struct timespec stop;
    long long nanoseconds;
    int status;

    if (argc != 3) {
        return 2;
    }
    repetitions = atoi(argv[1]);
    mode = argv[2];
    if (strcmp(mode, "bad") == 0) {
        length = 8;
        buffer = malloc(length);
        if (buffer == NULL) {
            return 3;
        }
        memcpy(buffer, "local =\n", length);
    } else if (strcmp(mode, "speed") == 0 && repetitions > 0) {
        length = (size_t)repetitions * 6u;
        buffer = malloc(length);
        if (buffer == NULL) {
            return 3;
        }
        for (int index = 0; index < repetitions; index++) {
            memcpy(buffer + (size_t)index * 6u, "x = 1\n", 6u);
        }
    } else {
        return 2;
    }
    state = luaL_newstate();
    if (state == NULL) {
        return 4;
    }
    clock_gettime(CLOCK_MONOTONIC, &start);
    status = luaL_loadbuffer(state, buffer, length, "chunk");
    clock_gettime(CLOCK_MONOTONIC, &stop);
    nanoseconds = (long long)(stop.tv_sec - start.tv_sec) * 1000000000LL
        + (long long)(stop.tv_nsec - start.tv_nsec);
    printf("rc=%d ns=%lld len=%zu\n", status, nanoseconds, length);
    return 0;
}
