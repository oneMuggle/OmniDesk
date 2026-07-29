import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useMemoData } from './useMemoData';
import memoApi from '../../../shared/api/memoApi';

jest.mock('../../../shared/api/memoApi');

const MOCK_MEMOS = [
  {
    id: 1,
    title: '备忘录一',
    content: '内容一',
    reminder_time: null,
    is_completed: false,
    user: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  },
  {
    id: 2,
    title: '备忘录二',
    content: '内容二',
    reminder_time: null,
    is_completed: true,
    user: 1,
    created_at: '2026-07-02T00:00:00Z',
    updated_at: '2026-07-02T00:00:00Z',
  },
];

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('useMemoData', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('memos 返回解包后的 Memo[](而非 AxiosResponse)', async () => {
    // memoApi.getAllMemos 返回 AxiosResponse 形状: { data: { results }, status, ... }
    memoApi.getAllMemos.mockResolvedValue({
      data: { results: MOCK_MEMOS },
      status: 200,
      statusText: 'OK',
      headers: {},
    });

    const { result } = renderHook(() => useMemoData(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(Array.isArray(result.current.memos)).toBe(true);
    expect(result.current.memos).toEqual(MOCK_MEMOS);
    // 回归断言:绝不能把整个 AxiosResponse 作为数据泄漏出去
    expect(result.current.memos.status).toBeUndefined();
    expect(result.current.error).toBeNull();
  });

  it('响应缺少 results 字段时回退为空数组', async () => {
    memoApi.getAllMemos.mockResolvedValue({ data: {}, status: 200 });

    const { result } = renderHook(() => useMemoData(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.memos).toEqual([]);
  });
});
