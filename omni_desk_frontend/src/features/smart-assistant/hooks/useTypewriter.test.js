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
