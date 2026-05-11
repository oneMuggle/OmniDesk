/*
 * plugin_sdk.h - C 语言插件 SDK
 * 所有 C 插件通过 stdin/stdout JSON 协议通信
 */
#ifndef PLUGIN_SDK_H
#define PLUGIN_SDK_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char* plugin_read_input(void) {
    size_t capacity = 4096;
    size_t len = 0;
    char* buf = malloc(capacity);
    if (!buf) return NULL;
    int c;
    while ((c = getchar()) != EOF) {
        if (len + 1 >= capacity) {
            capacity *= 2;
            char* new_buf = realloc(buf, capacity);
            if (!new_buf) { free(buf); return NULL; }
            buf = new_buf;
        }
        buf[len++] = (char)c;
    }
    buf[len] = '\0';
    return buf;
}

static void plugin_output(const char* json_result) {
    printf("%s\n", json_result);
    fflush(stdout);
}

static void plugin_error(const char* message, int exit_code) {
    fprintf(stderr, "%s\n", message);
    exit(exit_code);
}

#endif
