/**
 * usePaperlessHealth 单测(R4-D1)。
 *
 * 覆盖:初始状态 / 健康响应 / 不健康响应 / 请求失败 / 30s 轮询 / 卸载清理。
 * mock axiosInstance,用 fake timers 推进轮询间隔。
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import axiosInstance from '../../../../shared/api/axiosConfig';
import { usePaperlessHealth } from '../usePaperlessHealth';

jest.mock('../../../../shared/api/axiosConfig', () => ({
  get: jest.fn(),
}));

describe('usePaperlessHealth', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('初始状态:isHealthy=true, loading=true', () => {
    axiosInstance.get.mockResolvedValue({ data: { is_healthy: true } });

    const { result } = renderHook(() => usePaperlessHealth());

    expect(result.current).toEqual({ isHealthy: true, loading: true });
  });

  it('健康响应 → isHealthy=true, loading=false', async () => {
    axiosInstance.get.mockResolvedValue({ data: { is_healthy: true } });

    const { result } = renderHook(() => usePaperlessHealth());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isHealthy).toBe(true);
  });

  it('is_healthy=false → isHealthy=false', async () => {
    axiosInstance.get.mockResolvedValue({ data: { is_healthy: false } });

    const { result } = renderHook(() => usePaperlessHealth());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isHealthy).toBe(false);
  });

  it('请求失败 → isHealthy=false', async () => {
    axiosInstance.get.mockRejectedValue(new Error('paperless down'));

    const { result } = renderHook(() => usePaperlessHealth());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isHealthy).toBe(false);
  });

  it('每 30s 重新检查一次健康状态', async () => {
    jest.useFakeTimers();
    axiosInstance.get.mockResolvedValue({ data: { is_healthy: true } });

    renderHook(() => usePaperlessHealth());
    await act(async () => { await Promise.resolve(); });

    // mount 后立即检查一次
    expect(axiosInstance.get).toHaveBeenCalledTimes(1);
    expect(axiosInstance.get).toHaveBeenCalledWith('/paperless/health/');

    // 推进 30s → 触发第二次
    await act(async () => { jest.advanceTimersByTime(30000); });
    expect(axiosInstance.get).toHaveBeenCalledTimes(2);
  });

  it('卸载后清除定时器,不再发起检查', async () => {
    jest.useFakeTimers();
    axiosInstance.get.mockResolvedValue({ data: { is_healthy: false } });

    const { result, unmount } = renderHook(() => usePaperlessHealth());
    await act(async () => { await Promise.resolve(); });

    unmount();
    // 卸载后推进 60s,cancelled 标志应阻止后续请求
    await act(async () => { jest.advanceTimersByTime(60000); });
    expect(axiosInstance.get).toHaveBeenCalledTimes(1);
    // 且卸载后状态不再更新(不抛 setState on unmounted 警告)
    expect(result.current.isHealthy).toBe(false);
  });
});