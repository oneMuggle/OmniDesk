import { useRef, useCallback, useEffect } from 'react';

/**
 * 打字机状态机 hook。
 * 封装 requestAnimationFrame 循环 + 渐进揭示 + 完成回调分发,
 * 让 SmartChatPage 不必直接管理 rAF 与一组同步 ref。
 *
 * @param {object} opts
 * @param {(displayed: string) => void} opts.onTick  每帧揭示时触发(ref → ref,不引入额外 re-render)
 * @param {number} [opts.intervalMs=30]  渐进速率阈值(原 TYPEWRITER_INTERVAL)
 * @returns {{
 *   append: (text: string) => void,
 *   markCached: () => void,
 *   beginStreaming: () => void,
 *   markStreamingEnd: () => void,
 *   cancel: () => void,
 *   onComplete: (cb: () => void) => () => void,
 *   flush: () => void,
 *   isComplete: () => boolean,
 *   getReceived: () => string,
 * }}
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
  const tickRef = useRef(null);

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
      rafRef.current = requestAnimationFrame(tickRef.current);
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

    rafRef.current = requestAnimationFrame(tickRef.current);
  }, [onTick, intervalMs]);

  // 同步 tick 函数引用到 tickRef,避免闭包失效
  useEffect(() => {
    tickRef.current = tick;
  }, [tick]);

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
        rafRef.current = requestAnimationFrame(tickRef.current);
      }
    },
    [onTick]
  );

  const markCached = useCallback(() => {
    isCachedRef.current = true;
  }, []);

  const markStreamingEnd = useCallback(() => {
    isStreamingRef.current = false;
    // 若已显示完整,立即触发 onComplete(对应"流已结束 + 显示完整"路径)
    if (displayedLenRef.current >= receivedTextRef.current.length) {
      if (completedFiredRef.current) {
        return; // 防重复触发
      }
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      completeCallbacksRef.current.forEach((cb) => cb());
      completeCallbacksRef.current = [];
      completedFiredRef.current = true;
    }
  }, []);

  const beginStreaming = useCallback(() => {
    isStreamingRef.current = true;
    completedFiredRef.current = false;
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

  /**
   * 同步读取 hook 内部累积的完整已接收文本(SSE chunk 累积缓冲)。
   * 与 onTick → setStreamingAnswer(异步 React state)不同,本方法在调用栈内
   * 立即可读,适用于 done 兜底等需要在同一轮同步循环内判断"流是否已产出正文"的场景。
   * @returns {string} hook 内部累积的完整已接收文本(同步可读)
   */
  const getReceived = useCallback(() => receivedTextRef.current, []);

  // 组件卸载时清理 rAF
  useEffect(() => {
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, []);

  return { append, markCached, beginStreaming, markStreamingEnd, cancel, onComplete, flush, isComplete, getReceived };
}
