/**
 * useCrudQuery 单测(R5-D6)。
 *
 * 覆盖:透传 data/isLoading/refetch、extractResults 收口({results} 与裸数组)、
 * 失败时 message.error 提示与默认文案、options 透传(staleTime 覆盖)。
 */
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { message } from 'antd';
import React from 'react';
import { useCrudQuery } from './useCrudQuery';

jest.mock('antd', () => ({
  message: { error: jest.fn() },
}));

const renderWithClient = (hook) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  return renderHook(hook, { wrapper });
};

describe('useCrudQuery', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('fetcher 返回 {results, count} → data 为收口后的数组', async () => {
    const fetcher = jest.fn().mockResolvedValue({
      results: [{ id: 1 }, { id: 2 }],
      count: 2,
    });

    const { result } = renderWithClient(() => useCrudQuery(['t'], fetcher));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1 }, { id: 2 }]);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('fetcher 返回裸数组 → data 原样透传', async () => {
    const rows = [{ id: 1 }];
    const fetcher = jest.fn().mockResolvedValue(rows);

    const { result } = renderWithClient(() => useCrudQuery(['t'], fetcher));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe(rows);
  });

  it('加载中 isLoading=true,完成后为 false', async () => {
    const fetcher = jest.fn().mockResolvedValue([]);

    const { result } = renderWithClient(() => useCrudQuery(['t'], fetcher));

    // 挂载即进入 pending
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  it('fetcher 失败 → message.error 提示默认文案,error 透传', async () => {
    const fetcher = jest.fn().mockRejectedValue(new Error('网络错误'));

    const { result } = renderWithClient(() => useCrudQuery(['t'], fetcher));

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(message.error).toHaveBeenCalledWith('数据加载失败');
    expect(result.current.error).toBeInstanceOf(Error);
  });

  it('自定义错误文案经 options.errorMessage 生效', async () => {
    const fetcher = jest.fn().mockRejectedValue(new Error('x'));

    const { result } = renderWithClient(() =>
      useCrudQuery(['t'], fetcher, { errorMessage: '获取节假日列表失败' })
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(message.error).toHaveBeenCalledWith('获取节假日列表失败');
  });

  it('成功时不弹任何错误提示', async () => {
    const fetcher = jest.fn().mockResolvedValue({ results: [] });

    const { result } = renderWithClient(() => useCrudQuery(['t'], fetcher));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(message.error).not.toHaveBeenCalled();
  });

  it('options 透传 React Query(enabled=false 不发请求)', async () => {
    const fetcher = jest.fn().mockResolvedValue([]);

    renderWithClient(() => useCrudQuery(['t'], fetcher, { enabled: false }));

    await waitFor(() => expect(fetcher).not.toHaveBeenCalled());
  });

  it('refetch 可用并重新调用 fetcher', async () => {
    const fetcher = jest.fn().mockResolvedValue([{ id: 1 }]);

    const { result } = renderWithClient(() => useCrudQuery(['t'], fetcher));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await result.current.refetch();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
