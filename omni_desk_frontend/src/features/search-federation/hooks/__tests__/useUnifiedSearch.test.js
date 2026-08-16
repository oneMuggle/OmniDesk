/**
 * useUnifiedSearch 单测(R4-D2)。
 *
 * mock unifiedSearch,覆盖:空 query 短路 / 正常搜索 / 降级标记 / 请求失败。
 */
import { renderHook, act } from '@testing-library/react';
import { unifiedSearch } from '../../api/searchApi';
import { useUnifiedSearch } from '../useUnifiedSearch';

jest.mock('../../api/searchApi', () => ({
  unifiedSearch: jest.fn(),
}));

describe('useUnifiedSearch', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('初始状态:空结果、未降级、未加载', () => {
    const { result } = renderHook(() => useUnifiedSearch());

    expect(result.current).toEqual({
      results: [],
      degraded: false,
      loading: false,
      search: expect.any(Function),
    });
  });

  it('空 query 不调用 API,直接清空结果', async () => {
    const { result } = renderHook(() => useUnifiedSearch());

    await act(async () => { await result.current.search('   '); });

    expect(unifiedSearch).not.toHaveBeenCalled();
    expect(result.current.results).toEqual([]);
    expect(result.current.degraded).toBe(false);
  });

  it('搜索成功 → 填充结果并标记降级状态', async () => {
    unifiedSearch.mockResolvedValue({
      results: [{ id: 1, title: '年度报告' }],
      degraded: true,
    });
    const { result } = renderHook(() => useUnifiedSearch());

    await act(async () => { await result.current.search('报告'); });

    expect(result.current.results).toEqual([{ id: 1, title: '年度报告' }]);
    expect(result.current.degraded).toBe(true);
    expect(result.current.loading).toBe(false);
  });

  it('搜索失败 → 清空结果、取消降级标记、不抛错', async () => {
    unifiedSearch.mockRejectedValue(new Error('federation down'));
    const { result } = renderHook(() => useUnifiedSearch());

    await act(async () => { await result.current.search('报告'); });

    expect(result.current.results).toEqual([]);
    expect(result.current.degraded).toBe(false);
    expect(result.current.loading).toBe(false);
  });
});