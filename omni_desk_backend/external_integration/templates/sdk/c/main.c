/* main.c - C 插件示例 */
#include "plugin_sdk.h"

int main(void) {
    char* input = plugin_read_input();
    if (!input) {
        plugin_error("Failed to read input", 1);
    }
    /* TODO: 解析 input JSON 并实现业务逻辑 */
    plugin_output("{\"status\":\"success\",\"result\":{}}");
    free(input);
    return 0;
}
