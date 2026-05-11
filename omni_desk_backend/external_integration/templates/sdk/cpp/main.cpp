/* main.cpp - C++ 插件示例 */
#include <iostream>
#include <string>
#include <sstream>

namespace plugin {

static std::string read_input() {
    std::string result;
    std::string line;
    while (std::getline(std::cin, line)) {
        result += line;
    }
    return result;
}

static void output(const std::string& json) {
    std::cout << json << std::endl;
}

static void error(const std::string& msg, int code) {
    std::cerr << msg << std::endl;
    exit(code);
}

} // namespace plugin

int main() {
    std::string input = plugin::read_input();
    if (input.empty()) {
        plugin::error("Failed to read input", 1);
    }
    /* TODO: 解析 input JSON 并实现业务逻辑 */
    plugin::output(R"({"status":"success","result":{}})");
    return 0;
}
