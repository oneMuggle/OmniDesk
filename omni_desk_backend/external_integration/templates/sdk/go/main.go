// main.go - Go 插件示例
// 所有 Go 插件通过 stdin/stdout JSON 协议通信
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

type PluginInput struct {
	Action string                 `json:"action"`
	Params map[string]interface{} `json:"params"`
}

type PluginOutput struct {
	Status string      `json:"status"`
	Result interface{} `json:"result"`
}

func main() {
	reader := bufio.NewReader(os.Stdin)
	input, err := reader.ReadString('\n')
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read input: %v\n", err)
		os.Exit(1)
	}

	var pluginInput PluginInput
	if err := json.Unmarshal([]byte(strings.TrimSpace(input)), &pluginInput); err != nil {
		fmt.Fprintf(os.Stderr, "Invalid JSON input: %v\n", err)
		os.Exit(1)
	}

	// TODO: 实现业务逻辑

	output := PluginOutput{
		Status: "success",
		Result: map[string]interface{}{},
	}

	out, _ := json.Marshal(output)
	fmt.Println(string(out))
}
