import { renderHook, act } from '@testing-library/react';
import { useTypewriter } from './useTypewriter';

describe('useTypewriter', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

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

  it('流结束 + 已显示完整 → onComplete 触发一次', () => {
    const cb = jest.fn();
    const { result } = renderHook(() => useTypewriter({ intervalMs: 10 }));
    act(() => result.current.beginStreaming());
    act(() => result.current.onComplete(cb));
    act(() => result.current.append('你好世界'));
    act(() => jest.advanceTimersByTime(200));
    act(() => result.current.markStreamingEnd());

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
});