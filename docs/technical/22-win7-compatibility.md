# Win7 兼容性方案

## 1. 目标

内网部署需支持 Windows 7 浏览器（Chrome 109 / Edge 109 最大版本）。

## 2. 前端兼容

| 要求 | 措施 |
|------|------|
| 不主动放弃 IE11 | 避免使用 IE11 不支持的语法 |
| Chrome 109 | 不使用 ES2023+ 语法 |
| CSS | 避免 `:has()`、container queries 等新特性 |
| 构建 | 编译目标设旧版浏览器，Polyfill 自动注入 |
| 动态 `import()` / `React.lazy` | ✅ 支持 | Chrome 61+,与 Win7 Chrome 109 兼容 |

## 3. 桌面客户端兼容

| 要求 | 措施 |
|------|------|
| Python 3.8 | 依赖锁定兼容版本 |
| PyQt5 | 替代 PyQt6，适配 API 差异 |
| PyInstaller | spec 文件生成单文件可执行程序 |
