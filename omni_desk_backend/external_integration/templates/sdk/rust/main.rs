// main.rs - Rust 插件示例
// 所有 Rust 插件通过 stdin/stdout JSON 协议通信
use std::io::{self, BufRead, Write};

fn main() {
    let stdin = io::stdin();
    let mut input = String::new();
    stdin.lock().read_line(&mut input).expect("Failed to read input");

    // TODO: 解析 input JSON 并实现业务逻辑

    let output = r#"{"status":"success","result":{}}"#;
    println!("{}", output);
    io::stdout().flush().unwrap();
}
