# useTypewriter Hook 抽取与 SSE 收尾回归测试 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 SmartChatPage 内散落的 typewriter 状态机抽成 `useTypewriter` hook,使 typewriter 收尾等待路径与 60s 超时兜底可独立单元测,同时让 SmartChatPage 责任收敛(SSE 读取 / typewriter / 消息列表三件事各归其位)。

**Architecture:**
- 新增 `useTypewriter` hook(纯 ref + onComplete 回调),对外暴露 `append / markCached / beginStreaming / markStreamingEnd / cancel / onComplete / flush / isComplete` 8 个方法
- SmartChatPage 删 7 个 ref + 3 个 useCallback,改用 hook 实例替换
- 新增 hook 单元测(6 用例,fake timer 推进)
- 在 UX 集成测用 `jest.useFakeTimers()` 替代 `requestAnimationFrame = () => 0` 假值,保留现有 3 个用例 + 新增 1 个 typewriter 自然收尾用例

**Tech Stack:** React 18.3、@testing-library/react 18(`renderHook` from `@testing-library/react`)、jest fake timers

## Global Constraints

- 分支:`fix/sa-typewriter-hook-tests`(基于 main 创建)
- 不动产品样式(`SmartChatPage.css`)
- 不抽 `useStreamTimeout`(留在 `runStream` 内) / 不抽 SSE 解析(纯函数内联即可)
- 保持 typewriter 渐进速率算法不变:`Math.max(1, Math.min(Math.ceil(remaining * 0.2), 10))`
- 保持 60s 超时阈值不变:`STREAM_TIMEOUT_MS = 60_000`
- 不引入新 npm 依赖
- 不引入 console.log / debug 代码
- 所有 UX 测试断言保持"按钮复位 + 完整文本出现"语义不变
- commit message 走 conventional commits 格式
- 每个任务结束后独立 commit

---

## File Structure

| 文件 | 职责 |
|---|---|
| `src/features/smart-assistant/hooks/useTypewriter.js`(新建) | typewriter 状态机,封装 rAF + ref + onComplete 回调分发 |
| `src/features/smart-assistant/hooks/useTypewriter.test.js`(新建) | hook 单元测,6 用例,fake timer |
| `src/features/smart-assistant/pages/SmartChatPage.jsx`(修改) | 删 7 ref + 3 useCallback,改用 hook;`runStream` finally 改用 `typewriter.onComplete`;`handleStop` 改用 `typewriter.cancel` |
| `src/features/smart-assistant/pages/__tests__/SmartChatPage.ux.test.jsx`(修改) | `requestAnimationFrame = () => 0` 假值替换为 `jest.useFakeTimers()`,保留 3 用例 + 新增 1 个 typewriter 收尾用例 |

---

## Task 1: 创建 `useTypewriter` hook 骨架与最简 append 测试

**Files:**
- Create: `omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.js`
- Create: `omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.test.js`

**Interfaces:**
- Produces:
  - `useTypewriter({ onTick, intervalMs = 30 })` returns `{ append, markCached, markStreamingEnd, cancel, onComplete, flush, isComplete }`

- [ ] **Step 1.1: 创建 hook 测试文件骨架**

`omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.test.js`:

```js
import { renderHook, act } from '@testing-library/react';
import { useTypewriter } from './useTypewriter';

describe('useTypewriter', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it('append 累积文本并通过 onTick 暴露完整已显示内容', () => {
    const onTick = jest.fn();
    const { result } = renderHook(() =>
      useTypewriter({ onTick, intervalMs: 30 })
    );

    act(() => result.current.append('你好'));

    // 未跨过 intervalMs → onTick 暂未触发(append 自身不触发 tick)
    expect(onTick).not.toHaveBeenCalled();

    act(() => jest.advanceTimersByTime(50));

    // 跨过 intervalMs → onTick 触发,displayedLen > 0
    expect(onTick).toHaveBeenCalled();
    expect(onTick.mock.calls.at(-1)[0].length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 1.2: 运行测试验证失败**

```bash
cd omni_desk_frontend && npm test -- src/features/smart-assistant/hooks/useTypewriter.test.js
```

Expected: FAIL with "Cannot find module './useTypewriter'" 或 "useTypewriter is not a function"

- [ ] **Step 1.3: 创建 hook 骨架(支持 append + onTick)**

`omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.js`:

```js
import { useRef, useCallback, useEffect } from 'react';

/**
 * 打字机状态机 hook。
 * 封装 requestAnimationFrame 循环 + 渐进揭示 + 完成回调分发,
 * 让 SmartChatPage 不必直接管理 rAF 与一组同步 ref。
 *
 * @param {object} opts
 * @param {(displayed: string) => void} opts.onTick  每帧揭示时触发(ref → ref,不引入额外 re-render)
 * @param {number} [opts.intervalMs=30]  渐进速率阈值(原 TYPEWRITER_INTERVAL)
 */
export function useTypewriter({ onTick, intervalMs = 30 } = {}) {
  const rafRef = useRef(null);
  const receivedTextRef = useRef('');
  const displayedLenRef = useRef(0);
  const isCachedRef = useRef(false);
  const isStreamingRef = useRef(false);
  const lastTickRef = useRef(0);
  const completeCallbacksRef = useRef([]);
  const completedFiredRef = useRef(false);

  const tick = useCallback(() => {
    const received = receivedTextRef.current;
    const displayedLen = displayedLenRef.current;

    if (displayedLen >= received.length) {
      if (!isStreamingRef.current) {
        rafRef.current = null;
        completeCallbacksRef.current.forEach((cb) => cb());
        completeCallbacksRef.current = [];
        completedFiredRef.current = true;
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    const now = performance.now();
    if (now - lastTickRef.current >= intervalMs) {
      const remaining = received.length - displayedLen;
      const charsToAdd = Math.max(1, Math.min(Math.ceil(remaining * 0.2), 10));
      const newLen = Math.min(displayedLen + charsToAdd, received.length);

      displayedLenRef.current = newLen;
      lastTickRef.current = now;
      if (onTick) onTick(received.slice(0, newLen));
    }

    rafRef.current = requestAnimationFrame(tick);
  }, [onTick, intervalMs]);

  const append = useCallback(
    (text) => {
      receivedTextRef.current += text;
      if (isCachedRef.current) {
        const full = receivedTextRef.current;
        displayedLenRef.current = full.length;
        if (onTick) onTick(full);
        return;
      }
      if (!rafRef.current) {
        lastTickRef.current = performance.now();
        rafRef.current = requestAnimationFrame(tick);
      }
    },
    [tick, onTick]
  );

  const markCached = useCallback(() => {
    isCachedRef.current = true;
  }, []);

  const markStreamingEnd = useCallback(() => {
    isStreamingRef.current = false;
  }, []);

  const cancel = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    // 对称 resolve:resetTypewriter 现行为是 cancel 时 resolve 所有 wait
    completeCallbacksRef.current.forEach((cb) => cb());
    completeCallbacksRef.current = [];
    completedFiredRef.current = true;
    receivedTextRef.current = '';
    displayedLenRef.current = 0;
    isCachedRef.current = false;
    isStreamingRef.current = false;
  }, []);

  const onComplete = useCallback((cb) => {
    completeCallbacksRef.current.push(cb);
    return () => {
      completeCallbacksRef.current = completeCallbacksRef.current.filter((c) => c !== cb);
    };
  }, []);

  const flush = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const full = receivedTextRef.current;
    if (displayedLenRef.current < full.length) {
      displayedLenRef.current = full.length;
      if (onTick) onTick(full);
    }
  }, [onTick]);

  const isComplete = useCallback(() => {
    return (
      displayedLenRef.current >= receivedTextRef.current.length && !isStreamingRef.current
    );
  }, []);

  // 组件卸载时清理 rAF
  useEffect(() => {
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, []);

  return { append, markCached, markStreamingEnd, cancel, onComplete, flush, isComplete };
}
```

- [ ] **Step 1.4: 运行测试验证通过**

```bash
cd omni_desk_frontend && npm test -- src/features/smart-assistant/hooks/useTypewriter.test.js
```

Expected: 1 passed

- [ ] **Step 1.5: Commit**

```bash
git add src/features/smart-assistant/hooks/useTypewriter.js src/features/smart-assistant/hooks/useTypewriter.test.js
git commit -m "feat(smart-assistant): useTypewriter hook 骨架 + append onTick 单测"
```

---

## Task 2: hook 自然完成 + 流未结束不触发 onComplete 测试

**Files:**
- Modify: `omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.test.js`
- Modify: `omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.js`(新增 `beginStreaming()` 接口 + `markStreamingEnd` 立即触发 onComplete)

**Interfaces:**
- Consumes: `useTypewriter` 返回的 `append / beginStreaming / markStreamingEnd / onComplete / isComplete`
- Produces: 修复 hook 在自然完成时调用 `onComplete`,流未结束时不调用

- [ ] **Step 2.1: 修正 Task 1 的测试为正确语义,新增 beginStreaming 测试**

把 Task 1.1 的测试替换为:

```js
it('append 累积文本并通过 onTick 暴露已显示内容', () => {
  const onTick = jest.fn();
  const { result } = renderHook(() =>
    useTypewriter({ onTick, intervalMs: 30 })
  );

  act(() => result.current.beginStreaming());
  act(() => result.current.append('你好'));

  // 未跨过 intervalMs → onTick 暂未触发
  expect(onTick).not.toHaveBeenCalled();

  act(() => jest.advanceTimersByTime(50));

  // 跨过 intervalMs → onTick 触发
  expect(onTick).toHaveBeenCalled();
  expect(onTick.mock.calls.at(-1)[0].length).toBeGreaterThan(0);
});
```

- [ ] **Step 2.2: 新增 beginStreaming + markStreamingEnd 接口**

编辑 `useTypewriter.js`,在 `markStreamingEnd` 旁新增 `beginStreaming`:

```js
const beginStreaming = useCallback(() => {
  isStreamingRef.current = true;
  completedFiredRef.current = false;
}, []);
```

并把 `markStreamingEnd` 改为:

```js
const markStreamingEnd = useCallback(() => {
  isStreamingRef.current = false;
  // 若已显示完整,立即触发 onComplete(对应"流已结束 + 显示完整"路径)
  if (displayedLenRef.current >= receivedTextRef.current.length) {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    completeCallbacksRef.current.forEach((cb) => cb());
    completeCallbacksRef.current = [];
    completedFiredRef.current = true;
  }
}, []);
```

在 return 中加入 `beginStreaming`。

- [ ] **Step 2.3: 追加两个测试用例**

```js
it('流结束 + 已显示完整 → onComplete 触发一次', () => {
  const { result } = renderHook(() => useTypewriter({ intervalMs: 10 }));
  act(() => result.current.beginStreaming());
  act(() => result.current.append('你好世界'));
  act(() => jest.advanceTimersByTime(200));
  act(() => result.current.markStreamingEnd());

  const cb = jest.fn();
  act(() => result.current.onComplete(cb));
  expect(cb).toHaveBeenCalledTimes(1);
});

it('流未结束 + 已显示完整 → onComplete 不触发', () => {
  const { result } = renderHook(() => useTypewriter({ intervalMs: 10 }));
  act(() => result.current.beginStreaming());
  act(() => result.current.append('你好世界'));
  act(() => jest.advanceTimersByTime(200));

  const cb = jest.fn();
  act(() => result.current.onComplete(cb));
  expect(cb).not.toHaveBeenCalled();

  // 标记流结束后,cb 才被调用
  act(() => result.current.markStreamingEnd());
  expect(cb).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2.4: 运行测试验证通过**

```bash
cd omni_desk_frontend && npm test -- src/features/smart-assistant/hooks/useTypewriter.test.js
```

Expected: 3 passed(Task 1 的 1 个 + 本任务的 2 个)

- [ ] **Step 2.5: Commit**

```bash
git add src/features/smart-assistant/hooks/useTypewriter.js src/features/smart-assistant/hooks/useTypewriter.test.js
git commit -m "feat(smart-assistant): useTypewriter beginStreaming + markStreamingEnd 立即触发 onComplete"
```

---

## Task 3: hook cancel / markCached / flush 测试

**Files:**
- Modify: `omni_desk_frontend/src/features/smart-assistant/hooks/useTypewriter.test.js`

**Interfaces:**
- Consumes: `useTypewriter` 返回的 `cancel / markCached / flush / onComplete`
- Produces: hook 单元测覆盖剩余 3 个边界

- [ ] **Step 3.1: 追加 3 个测试用例**

在 `useTypewriter.test.js` 的 describe 末尾追加:

```js
it('cancel 触发 onComplete(对称 resolve)', () => {
  const { result } = renderHook(() => useTypewriter({ intervalMs: 10 }));
  act(() => result.current.beginStreaming());
  act(() => result.current.append('正在显示'));
  act(() => jest.advanceTimersByTime(50));

  const cb = jest.fn();
  act(() => result.current.onComplete(cb));
  act(() => result.current.cancel());
  expect(cb).toHaveBeenCalledTimes(1);
});

it('markCached 后 append 立即全量显示', () => {
  const onTick = jest.fn();
  const { result } = renderHook(() =>
    useTypewriter({ onTick, intervalMs: 30 })
  );

  act(() => result.current.markCached());
  act(() => result.current.append('完整缓存回答'));
  expect(onTick).toHaveBeenCalledWith('完整缓存回答');
  expect(result.current.isComplete()).toBe(true);
});

it('flush(流结束后 raf 未启动)立即触发 onComplete', () => {
  const { result } = renderHook(() => useTypewriter({ intervalMs: 30 }));

  act(() => result.current.append('helloworld'));

  const cb = jest.fn();
  act(() => result.current.onComplete(cb));
  act(() => result.current.flush());
  act(() => result.current.markStreamingEnd());
  expect(cb).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 3.2: 运行测试验证通过**

```bash
cd omni_desk_frontend && npm test -- src/features/smart-assistant/hooks/useTypewriter.test.js
```

Expected: 6 passed

- [ ] **Step 3.3: 若失败按错误信息补 hook 实现**

`cancel` 已在 Task 1.3 中实现对称 resolve,直接通过。`markCached` 已在 Task 1.3 中支持。`flush` 与 `markStreamingEnd` 组合已在 Task 2.2 中支持。

- [ ] **Step 3.4: Commit**

```bash
git add src/features/smart-assistant/hooks/useTypewriter.js src/features/smart-assistant/hooks/useTypewriter.test.js
git commit -m "test(smart-assistant): useTypewriter cancel / markCached / flush 单测"
```

---

## Task 4: SmartChatPage 适配 hook — 删 ref + 用 hook 替换

**Files:**
- Modify: `omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx`

**Interfaces:**
- Consumes: `useTypewriter` 的全部 8 个方法(`append / markCached / beginStreaming / markStreamingEnd / cancel / onComplete / flush / isComplete`)
- Produces: SmartChatPage.jsx 净减 ≥ 20 行;`runStream` finally 用 hook 接口替代原 `!rafRef.current` + `waitTypewriterResolveRef` 等待

- [ ] **Step 4.1: 删除 SmartChatPage 内 7 个 ref + 3 个 useCallback**

在 `omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx`:

- 删除 `L110-150` 范围内的 7 个 ref:`rafRef / receivedTextRef / displayedLenRef / isCachedRef / isStreamingRef / lastTickRef / waitTypewriterResolveRef`
- 删除 `typewriterTick` (`L225-258`)、`resetTypewriter` (`L261-278`)、`flushTypewriter` (`L280-291`) 三个 useCallback
- 删除组件卸载清理 rAF 的 useEffect(`L151-156`)(已搬入 hook)

- [ ] **Step 4.2: 在文件顶部 import hook**

```js
import { useTypewriter } from '../hooks/useTypewriter';
```

- [ ] **Step 4.3: 在组件内实例化 hook**

在组件顶部(原 ref 声明位置),替换为:

```js
const TYPEWRITER_INTERVAL = 30; // 保留为模块常量

const onTypewriterTick = useCallback(
  (displayed) => setStreamingAnswer(displayed),
  []
);

const typewriter = useTypewriter({
  onTick: onTypewriterTick,
  intervalMs: TYPEWRITER_INTERVAL,
});
```

- [ ] **Step 4.4: 修改 `handleMetaEvent`**

把:

```js
if (event.cache_hit) {
  isCachedRef.current = true;
  setStreamingAnswer(receivedTextRef.current);
  displayedLenRef.current = receivedTextRef.current.length;
}
```

改为:

```js
if (event.cache_hit) {
  typewriter.markCached();
}
```

- [ ] **Step 4.5: 修改 `handleChunkEvent`**

把:

```js
const handleChunkEvent = useCallback((event) => {
  receivedTextRef.current += event.content;
  if (isCachedRef.current) {
    setStreamingAnswer(receivedTextRef.current);
    displayedLenRef.current = receivedTextRef.current.length;
  } else if (!rafRef.current) {
    lastTickRef.current = performance.now();
    rafRef.current = requestAnimationFrame(typewriterTick);
  }
}, [typewriterTick]);
```

改为:

```js
const handleChunkEvent = useCallback((event) => {
  typewriter.append(event.content);
}, [typewriter]);
```

- [ ] **Step 4.6: 修改 `handleStop` 与 `handleSubmit` 内的 typewriter 复位**

`handleStop`(L585 附近)中 `resetTypewriter();` 改为 `typewriter.cancel();`

`handleSubmit`(L514-540)内 `resetTypewriter();` 改为 `typewriter.cancel();`

- [ ] **Step 4.7: 修改 `runStream` 进入循环处 + finally 块**

`runStream` 进入读取循环前(L462)增加:

```js
typewriter.beginStreaming();
```

`runStream` finally 块(L498-511)改为:

```js
} finally {
  if (timeoutId) clearTimeout(timeoutId);
  if (typewriter.isComplete()) {
    typewriter.flush();
  } else {
    await new Promise((resolve) => typewriter.onComplete(resolve));
  }
  typewriter.markStreamingEnd();
}
```

注意 `markStreamingEnd` 必须放在 await 之后。

- [ ] **Step 4.8: 调整 `handleSSEEvent` 失败兜底路径(L409-411)**

`receivedTextRef.current = '回答生成失败';` 改为 `typewriter.append('回答生成失败');`

- [ ] **Step 4.9: 本地验证 SmartChatPage 编译通过**

```bash
cd omni_desk_frontend && npm run lint
```

Expected: 无 error

- [ ] **Step 4.10: Commit**

```bash
git add src/features/smart-assistant/pages/SmartChatPage.jsx
git commit -m "refactor(smart-assistant): SmartChatPage 改用 useTypewriter hook"
```

---

## Task 5: 调整 SmartChatPage UX 测试 — 用 fake timers 替换 rAF 假值

**Files:**
- Modify: `omni_desk_frontend/src/features/smart-assistant/pages/__tests__/SmartChatPage.ux.test.jsx`

**Interfaces:**
- Consumes: SmartChatPage + useTypewriter hook 真实实现
- Produces: 现有 3 个 UX 测试用例保持通过(rAF 假值改为 fake timers)

- [ ] **Step 5.1: 修改 `beforeAll` 全局 mock**

把:

```js
beforeAll(() => {
  window.requestAnimationFrame = () => 0;
  window.cancelAnimationFrame = jest.fn();
  Element.prototype.scrollIntoView = jest.fn();
  // ...
});
```

改为:

```js
beforeAll(() => {
  jest.useFakeTimers();
  Element.prototype.scrollIntoView = jest.fn();
  // ...
});

afterAll(() => {
  jest.useRealTimers();
});
```

- [ ] **Step 5.2: 修改"resets button and shows full answer"用例**

现有"shows stop button"用例(L74-94)无需改动。

"renders think content separately"(L95-135)无需改动。

"resets button and shows full answer"(L136-166)需要在 `findByText` 之后推进 typewriter 帧:

```js
// 内容显示完整(非部分 streamingAnswer)
await screen.findByText('完整回答内容', {}, { timeout: 3000 });
// 推进 typewriter 帧(原假值 rAF 直接 flush,现在用 fake timer 推进)
act(() => {
  jest.advanceTimersByTime(100);
});
// 按钮复位:"发送"恢复、无"取消"
await screen.findByRole('button', { name: '发送' }, { timeout: 3000 });
expect(screen.queryByRole('button', { name: '取消' })).not.toBeInTheDocument();
```

在文件顶部 import 中加 `import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';`

- [ ] **Step 5.3: 运行 UX 测试验证通过**

```bash
cd omni_desk_frontend && npm test -- src/features/smart-assistant/pages/__tests__/SmartChatPage.ux.test.jsx
```

Expected: 3 passed

- [ ] **Step 5.4: Commit**

```bash
git add src/features/smart-assistant/pages/__tests__/SmartChatPage.ux.test.jsx
git commit -m "test(smart-assistant): UX 测试改用 jest fake timers"
```

---

## Task 6: 新增 typewriter 自然收尾 UX 集成测

**Files:**
- Modify: `omni_desk_frontend/src/features/smart-assistant/pages/__tests__/SmartChatPage.ux.test.jsx`

**Interfaces:**
- Consumes: SmartChatPage + useTypewriter hook + fake timers
- Produces: 验证"流结束后 typewriter 自然完成,runStream 才推入消息 + 复位按钮"

- [ ] **Step 6.1: 追加 1 个新测试用例**

在 `SmartChatPage.ux.test.jsx` describe 块末尾追加:

```js
it('typewriter 自然收尾后才推入消息 + 复位按钮', async () => {
  const { sendSmartChatStream } = require('../../api/smartAssistantApi');

  sendSmartChatStream.mockReturnValue({
    bodyPromise: Promise.resolve(
      createMockStream([
        { type: 'meta', intent: 'general', tool_used: null, tool_result: null, tool_fallback: false },
        { type: 'chunk', content: '你好世界' },
        { type: 'done', error: false },
        { type: 'session', conversation_id: 'cid-2', error: false, log_id: 2 },
      ])
    ),
    abort: jest.fn(),
  });

  renderWithProviders(<SmartChatPage />);

  const input = screen.getByPlaceholderText(/问我任何问题/);
  fireEvent.change(input, { target: { value: '测试 typewriter' } });
  fireEvent.click(screen.getByRole('button', { name: '发送' }));

  // 推进 typewriter 帧
  await act(async () => {
    jest.advanceTimersByTime(200);
  });

  // 验证:最终内容完整显示 + 按钮复位
  await screen.findByText('你好世界', {}, { timeout: 3000 });
  await screen.findByRole('button', { name: '发送' }, { timeout: 3000 });
  expect(screen.queryByRole('button', { name: '取消' })).not.toBeInTheDocument();
});
```

- [ ] **Step 6.2: 运行 UX 测试验证通过**

```bash
cd omni_desk_frontend && npm test -- src/features/smart-assistant/pages/__tests__/SmartChatPage.ux.test.jsx
```

Expected: 4 passed(3 旧 + 1 新)

- [ ] **Step 6.3: Commit**

```bash
git add src/features/smart-assistant/pages/__tests__/SmartChatPage.ux.test.jsx
git commit -m "test(smart-assistant): typewriter 自然收尾 UX 集成测"
```

---

## Task 7: 全量回归 + lint + 提 PR

**Files:**
- 无代码变更

**Interfaces:**
- Consumes: 上述 6 个任务的所有变更
- Produces: `fix/sa-typewriter-hook-tests` 分支,所有 CI 8 项绿,PR 待用户 merge

- [ ] **Step 7.1: 全量 smart_assistant 测试**

```bash
cd omni_desk_frontend && npm test -- src/features/smart-assistant/
```

Expected: 所有用例通过

- [ ] **Step 7.2: 全量 lint**

```bash
cd omni_desk_frontend && npm run lint
```

Expected: 无 error

- [ ] **Step 7.3: 构建检查**

```bash
cd omni_desk_frontend && npm run build
```

Expected: 成功(检查 routes.json 已生成)

- [ ] **Step 7.4: 推分支 + 创建 PR**

```bash
git push -u origin fix/sa-typewriter-hook-tests
gh pr create --title "refactor(smart-assistant): 抽取 useTypewriter hook + 补 typewriter 收尾专项测" --body "..."
```

- [ ] **Step 7.5: 监控 CI 至绿**

```bash
gh pr checks <pr-number> --watch
```

Expected: 8/8 绿

- [ ] **Step 7.6: 通知用户 merge**

向用户报告 CI 全绿 + 给出 PR 链接,等待 merge。

---

## Self-Review

### Spec 覆盖检查

| Spec 章节 | 对应 Task |
|---|---|
| §1 涉及文件 | Task 1-6 全部覆盖 |
| §2 hook 接口签名(7 方法 + beginStreaming) | Task 1 (append/onTick)、Task 2 (beginStreaming/markStreamingEnd)、Task 3 (cancel/markCached/flush)、Task 4 (整体适配含 onComplete/flush/isComplete) |
| §3 内部状态(refs) | Task 1 骨架、Task 2 beginStreaming/markStreamingEnd、Task 4 卸载清理 |
| §4 状态机时序 | Task 1 (append → rAF 启动)、Task 2 (markStreamingEnd → onComplete)、Task 3 (cancel → resolve、flush → 立即显示) |
| §5 cancel 时序 | Task 1.3 cancel 实现 + Task 3 cancel 测试 |
| §6 flush 时序 | Task 3 flush 测试 |
| §7 SmartChatPage 适配映射 | Task 4 全部映射 |
| §8 实施步骤(8 步) | Task 1-6 覆盖步骤 1-6,Task 7 覆盖步骤 7-8 |
| §9 hook 单测 6 用例 | Task 1 (1)、Task 2 (2)、Task 3 (3) = 6 用例 |
| §10 集成测新增 1 用例 | Task 6 |
| §11 风险与依赖 | 在每个 Task 的 Step 内体现 |
| §12 YAGNI(不做) | 全程未引入 useStreamTimeout / SSE 解析抽取 / 算法改动 / 新依赖 |
| §13 验收标准 | Task 7 全量 + 单文件验证 |

### Placeholder 扫描

- 无 "TBD" / "TODO" / "待定" / "implement later"
- 无 "Add appropriate error handling" 等模糊描述
- 每个代码块均给出实际可粘贴代码

### 类型一致性检查

- `append / markCached / beginStreaming / markStreamingEnd / cancel / onComplete / flush / isComplete` 在 Task 1/Task 2 定义,在 Task 4/Task 5/Task 6 使用,签名一致
- `useTypewriter({ onTick, intervalMs = 30 })` 签名在所有任务一致

### 一处 Gap 已修正

原 Spec §2 接口签名表未列 `beginStreaming`,但实施中发现必须显式暴露该方法(否则 `isStreamingRef` 永远 false,自然完成路径与原行为不一致)。Task 2 已补 `beginStreaming()` 接口,与原 SmartChatPage 进入读取循环时手动置 `isStreamingRef = true` 行为对齐。

Plan complete and saved to `docs/superpowers/plans/2026-08-12-sa-typewriter-hook.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

请选择执行方式。