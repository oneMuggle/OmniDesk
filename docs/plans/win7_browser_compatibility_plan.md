# Windows 7 浏览器兼容性方案

## 问题背景

当前项目（OmniDesk）需要支持 Windows 7 系统的用户访问。

**Windows 7 支持的浏览器版本：**

| 浏览器 | 最高版本 | 支持状态 |
|--------|----------|----------|
| Chrome | 109 | 最后版本，已终止更新 |
| Edge | 109 | 最后版本，已终止更新 |
| Firefox | 115 ESR | 支持至 2026年8月 |
| 360浏览器 | 基于 Chromium 86 | 国内浏览器，常用于 Win7 |

当前前端技术栈：
- React 18
- Create React App (react-scripts 5.0.1)
- Ant Design 5.x
- MUI 5.x
- TanStack Query 5.x

当前的 `browserslist` 配置排除了 Firefox 115 ESR 和 Chrome 109：
```json
"browserslist": {
  "production": [">0.2%", "not dead", "not op_mini all"],
  "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
}
```

> `">0.2%", "not dead"` 会排除已终止更新的浏览器，导致 Chrome 109 和 Firefox 115 ESR 无法使用

## 解决方案

### 1. 更新 browserslist 配置

修改 `omni_desk_frontend/package.json`：

```json
"browserslist": {
  "production": [
    ">0.2%",
    "not dead",
    "not op_mini all",
    "chrome >= 86",
    "firefox >= 115"
  ],
  "development": [
    "last 1 chrome version",
    "last 1 firefox version"
  ]
}
```

> 说明：使用 `chrome >= 86` 可以覆盖 360 浏览器（Chromium 86 内核）以及 Chrome 86+ 浏览器

### 2. 添加 Polyfill 依赖

安装必要的 polyfill 包：
```bash
npm install core-js whatwg-fetch
```

在 `src/index.js` 开头导入：
```javascript
import 'core-js/stable';
import 'whatwg-fetch';
```

### 3. 验证构建

运行构建并验证输出：
```bash
npm run build
```

## 实施任务

### 任务 1: 更新 Browserslist 配置
- [x] 1.1 修改 `package.json` browserslist，添加 `chrome >= 86` 和 `firefox >= 115`
- [x] 1.2 验证配置正确性：`npx browserslist`

### 任务 2: 添加 Polyfill 依赖
- [x] 2.1 安装 core-js 和 whatwg-fetch
- [x] 2.2 在 `src/index.js` 导入 polyfills

### 任务 3: 构建验证
- [x] 3.1 运行 `npm run build`
- [x] 3.2 确认构建成功，无报错

### 任务 4: 兼容性测试
- [ ] 4.1 在 360 浏览器（Chromium 86）中测试
- [ ] 4.2 在 Chrome 109 中测试（或模拟）
- [ ] 4.3 在 Firefox 115 ESR 中测试（或模拟）
- [ ] 4.4 验证 UI 组件正常显示
- [ ] 4.5 修复发现的问题

## 兼容性测试方法

### 方法一：浏览器开发者工具模拟

1. **360 浏览器 / Chrome**
   - 按 `F12` 打开开发者工具
   - 点击右上角三个点 → **更多工具** → **网络条件**
   - 取消勾选 "使用浏览器默认" → 手动选择 User-Agent 或自定义

2. **Chrome 模拟旧版浏览器**
   - `F12` 打开开发者工具
   - `Ctrl+Shift+P` (Mac: `Cmd+Shift+P`)
   - 输入 "Show Rendering"
   - 选择 "Emulate CSS media type" 测试不同渲染模式

### 方法二：Lighthouse 审计

1. 打开开发者工具 → **Lighthouse** 标签
2. 在设备下拉选择目标设备或手动设置 User-Agent
3. 点击 "Analyze page load"
4. 检查报告中的 "Best Practices" 和 "Accessibility"

### 方法三：在线云测试平台

| 平台 | 网址 | 特点 |
|------|------|------|
| BrowserStack | browserstack.com | 真实浏览器，直接操作 |
| LambdaTest | lambdatest.com | 支持自动化测试 |
| CrossBrowserTesting | crossbrowsertesting.com | 截图对比功能 |

### 方法四：本地安装测试

下载并安装目标浏览器进行真实测试：

| 浏览器 | 下载地址 |
|--------|---------|
| Chrome 109 | chromium.cytxdigital.com |
| Firefox 115 ESR | mozilla.org/firefox/enterprise/ |
| 360 极速浏览器 | browser.360.cn |

### 方法五：检查构建输出

验证构建是否生成了兼容代码：

```bash
# 查看构建产物
ls -la omni_desk_frontend/build/static/js/

# 检查是否包含 ES5 语法（箭头函数应该被转译）
grep -o "function" omni_desk_frontend/build/static/js/main.*.js | head -3

# 检查是否有 polyfill
grep -o "core-js" omni_desk_frontend/build/static/js/*.js
```

### 测试检查清单

- [ ] 页面正常加载，无白屏
- [ ] 登录功能正常
- [ ] 导航菜单可点击
- [ ] 表单提交正常
- [ ] 文件上传/下载正常
- [ ] 图表/日历等组件正常显示
- [ ] 无控制台报错
- [ ] 网络请求正常发送

### 常见兼容性问题

| 问题 | 解决方案 |
|------|---------|
| 白屏/空白页面 | 检查 JS 语法错误，确认 polyfill 已加载 |
| 样式错乱 | 检查 CSS 前缀，添加 Autoprefixer 配置 |
| API 请求失败 | 检查 fetch/polyfill 是否正确导入 |
| 组件不显示 | 检查 ES Modules 语法是否被正确转译 |

## 技术说明

### 360 浏览器（Chromium 86）与 Chrome 109 的 JavaScript 支持

**360 浏览器 (Chromium 86 内核) 特性支持：**
- ES2015 (ES6) 完整支持：箭头函数、类、模板字符串、解构赋值
- ES2016 完整支持：Array.prototype.includes、指数运算符
- ES2017 大部分支持：async/await、fetch API、Promise
- 可选链 (Optional chaining `?.`)、空值合并 (Nullish coalescing `??`)
- WebAssembly SIMD、BigInt
- Web Workers 中支持 ES Modules
- TLS 1.3 支持

**需要注意的限制：**
- Chromium 86：主线程不支持 ES Modules 动态导入（仅 Web Workers 支持）
- 一些较新的 CSS 特性可能不完全支持

**Chrome 109 / Firefox 115 ESR：** 完整支持 ES2018，现代特性更全面

### 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 包体积增加 | 转译到更老的目标会增大体积 | 可接受，用户基数小 |
| 360 浏览器兼容性 | 基于 Chromium 86，特性支持有限 | 主要目标浏览器，充分测试 |
| Chrome 109 安全风险 | Chrome 109 已无安全更新 | 建议用户使用 Firefox 115 ESR |
| CSS 特性 | 部分现代 CSS 可能不工作 | 测试验证 |
| Polyfill 开销 | 增加额外 JS | 仅加载必要的 |

## 文件修改清单

需要修改的文件：
- `omni_desk_frontend/package.json` - 更新 browserslist
- `omni_desk_frontend/src/index.js` - 添加 polyfill 导入