# useTypewriter Hook 抽取与 SSE 收尾回归测试 — 设计

> 文档日期: 2026-08-12
> 状态: 设计稿(待 user review)
> 关联 follow-up: 上次会话 (#203) 遗留的"前端超时兜底与 typewriter 收尾路径缺专项测试(需重构 rAF mock)"

## 背景与目标

PR #203 (`fix(chat): SSE 流式收尾兜底`) 修复了智能助手页面的按钮复位延迟问题,涉及三处新增逻辑:

1. **60s 兜底超时** (`runStream` 内 `setTimeout` + `reader.read()` 卡死时 abort)
2. **typewriter 收尾等待** (`runStream` finally 内 `await new Promise` 等打字机完成)
3. **`resetTypewriter` 对称 resolve** (取消按钮在 typewriter 显示期间点击时,不让 `runStream` 悬挂)

这些逻辑共用 **7 个 ref + 3 个 useCallback**,散落在 SmartChatPage 顶部,与 SSE 读取循环 / 消息列表 / UI 渲染混杂在一起。

**既有测试缺口**:
- 现有 UX 测试 (`SmartChatPage.ux.test.jsx:30`) 用 `requestAnimationFrame = () => 0` 假值绕过 rAF
- 导致 typewriter 永远不启动 → `runStream` 走 `flushTypewriter` 直接分支,**`waitTypewriterResolveRef` 等待路径从未被覆盖**
- 60s 超时兜底路径也没有针对性测试

**本文目标**: 把 typewriter 状态机抽成 `useTypewriter` hook,既能独立单元测试,又能让 SmartChatPage 责任收敛(SSE 读取 / typewriter / 消息列表三件事各归其位)。

## 涉及文件与模块

| 类型 | 路径 |
|---|---|
| 新增 | `omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.js` |
| 新增 | `omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.test.js` |
| 修改 | `omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx` |
| 修改 | `omni_desk_frontend/src/features/smart-assistant/pages/__tests__/SmartChatPage.ux.test.jsx` |

**不在改动范围**:
- `SmartChatPage.css` — 样式无关
- `runStream` 的 SSE 读取循环 / `parseSSE` / `handleSSEEvent` — 抽 hook 只动 typewriter 部分
- `api/smartAssistantApi` — mock 已存在,无需新增
- `SmartChatPage` 的消息列表 / UI 渲染 — 不动

## 技术方案

### hook 接口签名

```js
// hooks/useTypewriter.js
export function useTypewriter({
  onTick,        // (displayed: string) => void, 每帧揭示回调
  intervalMs = 30, // TYPEWRITER_INTERVAL
} = {}) {
  // 返回对象:
  return {
    append,            // (text: string) => void, 累积并启动 rAF
    markCached,        // () => void, 缓存命中:后续 append 立即全量显示
    markStreamingEnd,  // () => void, 流已结束:若已显示完整则触发 onComplete
    cancel,            // () => void, 取消(对称 resolve 所有 onComplete 回调)
    onComplete,        // (cb: () => void) => () => void, 注册一次性回调,返回取消注册函数
    flush,             // () => void, 立即显示全部(receive 兜底用)
    isComplete,        // () => boolean, 当前是否已显示完整(供 runStream 选择 flush vs 等待)
  };
}
```

### hook 内部状态(refs)

| ref | 用途 |
|---|---|
| `rafRef` | 当前 rAF 句柄 |
| `receivedTextRef` | 已接收完整文本 |
| `displayedLenRef` | 已显示字符数 |
| `isCachedRef` | 是否缓存命中 |
| `isStreamingRef` | 流是否仍在进行 |
| `lastTickRef` | 上次揭示时间戳 |
| `completeCallbacksRef` | 待触发的完成回调列表 |
| `completedFiredRef` | onComplete 是否已触发(防重复) |

### 状态机时序

```
   append(text)
     ↓
   receivedTextRef += text
     ↓
   if !isCached && !rafRef.current → 启动 rAF
     ↓
   每帧: displayedLen < received → 渐进; displayLen === received → 若 !isStreaming → 触发 onComplete
     ↓
   markStreamingEnd()
     ↓
   isStreamingRef = false
     ↓
   若 displayedLen === received → flush + 触发 onComplete
```

### cancel 时序(对称 resolve)

```
   cancel()
     ↓
   if rafRef → cancelAnimationFrame
     ↓
   立即触发所有 completeCallbacks (类似 resetTypewriter 现逻辑)
     ↓
   重置所有 ref (receivedTextRef='', displayedLenRef=0, ...)
```

### flush 时序(流结束兜底)

```
   flush()
     ↓
   if rafRef → cancelAnimationFrame
     ↓
   received → setStreamingAnswer(received)
     ↓
   displayedLenRef = received.length
```

### SmartChatPage 适配映射

| 旧代码 | 新代码 |
|---|---|
| `receivedTextRef.current += event.content` | `typewriter.append(event.content)` |
| `isCachedRef.current = true; setStreamingAnswer(receivedTextRef.current); displayedLenRef.current = receivedTextRef.current.length` | `typewriter.markCached()` |
| `lastTickRef.current = performance.now(); rafRef.current = requestAnimationFrame(typewriterTick)` | hook 内部处理(append 自动启动) |
| `if (!rafRef.current) { flushTypewriter(); } else { await new Promise((resolve) => { waitTypewriterResolveRef.current = resolve; }); }` | `if (typewriter.isComplete()) { typewriter.flush(); } else { await new Promise(...typewriter.onComplete 注册...) }` |
| `resetTypewriter()` (handleSubmit/handleStop) | `typewriter.cancel()` |
| `setStreamingAnswer(received)` (in typewriterTick) | hook 通过 `onTick` 回调传入 |

### onTick 回调的使用

```js
// SmartChatPage.jsx
const typewriter = useTypewriter({
  onTick: (displayed) => setStreamingAnswer(displayed),
  intervalMs: TYPEWRITER_INTERVAL,
});
```

`onTick` 由 hook 每帧揭示时同步触发(ref → ref,不引入额外 re-render,除非 setStreamingAnswer 真改了 state)。

## 实施步骤

- [ ] **步骤 1**: 创建 `useTypewriter.js` hook(包含状态机 + ref 集合 + 对外接口)
- [ ] **步骤 2**: 写 `useTypewriter.test.js` 单元测(6 个用例,见下表)
- [ ] **步骤 3**: 在 `SmartChatPage.jsx` 中调用 hook,删除原 7 个 ref + 3 个 useCallback
- [ ] **步骤 4**: 修改 `runStream` finally 块:`if (typewriter.isComplete()) { typewriter.flush(); } else { await new Promise((resolve) => typewriter.onComplete(resolve)); }`(用 hook 接口替代原 `!rafRef.current` + `waitTypewriterResolveRef` 等待)
- [ ] **步骤 5**: 调整 `SmartChatPage.ux.test.jsx`:用 `jest.useFakeTimers()` 替代 `requestAnimationFrame = () => 0` 假值,确保现有 3 个用例仍通过
- [ ] **步骤 6**: 在 UX 测追加 1 个新用例,验证 typewriter 自然收尾路径(`onComplete` 触发后才推入消息列表)
- [ ] **步骤 7**: 本地 `npm test -- src/features/smart-assistant/` 全量验证
- [ ] **步骤 8**: lint + CI 全绿

### hook 单元测用例清单

| 用例 | 验证 |
|---|---|
| append 后 advanceTimer 显示进度 | revealed 文本逐步增长 |
| 自然完成触发 onComplete | 流结束 + 全部显示后 cb 调用一次 |
| 流未结束时 onComplete 不触发 | `isStreaming=true` 时不会回调 |
| cancel 触发 onComplete(resolve 等待) | 模拟 handleStop 路径 |
| markCached 后 append 立即显示全量 | 缓存命中路径 |
| flush(流结束后 raf 未启动) | markStreamingEnd 后立即 onComplete |

### 集成测新增用例

| 用例 | 验证 |
|---|---|
| typewriter 收尾完成后才把消息推入列表 + 按钮复位 | 验证 `onComplete` 路径在端到端正确 |

## 风险与依赖

### 风险

- **onComplete 多次注册**:`runStream` finally 同步注册 + 异步 resolve 之间若重复调,旧注册会被新触发清空后,新注册不会重复触发(用 `completedFiredRef` flag 保证一次性)
- **cancel 后 append 是否安全**:cancel 会清空状态,后续 append 应重新启动 rAF(避免 handleStop 后再发送时 typewriter 不显示)。在 hook 内 `append` 检查 `rafRef` 是否被清空,若已清空则重启
- **backward compat**:UX 测试的 rAF 假值被替换为 fake timer,现有 3 个测试需小幅调整 — 但断言不变(都断言"按钮复位 + 完整文本出现")

### 依赖

- React 18.3 + jsdom test env(已配置)
- `jest.useFakeTimers()` 已用于其他测试文件(可借鉴)
- 无新依赖

## 不做(YAGNI)

- 不抽 `useStreamTimeout`(留在 `runStream` 内,与 abort 强耦合)
- 不抽 SSE 解析(纯函数,内联即可)
- 不改 typewriter 渐进速率算法(`Math.max(1, Math.min(Math.ceil(remaining * 0.2), 10))` 保持)
- 不改 60s 超时阈值(`STREAM_TIMEOUT_MS = 60_000` 保持)
- 不引入 `@testing-library/react-hooks`(React 18 内置 `renderHook` from `@testing-library/react` 即可)

## 验收标准

- [ ] `useTypewriter.test.js` 6 个用例全部通过
- [ ] `SmartChatPage.ux.test.jsx` 4 个用例(3 旧 + 1 新)全部通过
- [ ] 全量 `npm test` 无回归
- [ ] CI 8 项全绿
- [ ] SmartChatPage.jsx 净减行数(删 ref + useCallback,加 hook 调用)≥ 20 行
- [ ] 不引入 console.log / debug 代码

## 测试设计要点

### hook 单测的 fake timer 推进策略

```js
jest.useFakeTimers();
const { result } = renderHook(() => useTypewriter({ onTick }));

act(() => result.current.append('你好世界'));
// 期望: rAF 注册,onTick 暂未触发(intervalMs 未到)

act(() => jest.advanceTimersByTime(50)); // 跨过 intervalMs
// 期望: onTick 触发一次,displayedLen 增长

// 多次推进直到 received === displayed
while (!result.current.isComplete()) {
  act(() => jest.advanceTimersByTime(50));
}

act(() => result.current.markStreamingEnd());
// 期望: onComplete 触发
```

### 集成测的 fake timer 推进策略

UX 测试需要"内容显示完整" + "按钮复位"两个事件先后发生。fake timer + `act` 包 `findByText` / `findByRole` 的 waitFor 自然推进,无需手动 `jest.runAllTimers`。

## 与其他模块的关系

- 不影响 `runStream` 的 60s 超时兜底逻辑(继续留在 `runStream` 内)
- 不影响 SSE 解析 / `handleSSEEvent` / 消息列表
- 不影响 `handleStop` 的按钮状态机(只是把 `resetTypewriter()` 换成 `typewriter.cancel()`)
- 不影响后端任何代码

## 备注

本文档为设计稿,实施前需要 user 明确 review 通过。