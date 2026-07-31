import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import memoApi from '../../../shared/api/memoApi';

export const useMemoData = () => {
  const queryClient = useQueryClient();

  // 获取所有备忘录
  // memoApi.getAllMemos 返回 AxiosResponse,需解包 data.results;
  // 旧实现 queryFn 直接返回 AxiosResponse + select data.results(AxiosResponse
  // 上没有 results)导致 memos 永远为空数组
  const memosQuery = useQuery({
    queryKey: ['memos'],
    queryFn: async () => (await memoApi.getAllMemos()).data?.results ?? [],
  });

  // 创建备忘录
  const createMemoMutation = useMutation({
    mutationFn: memoApi.createMemo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memos'] });
    },
  });

  // 更新备忘录
  const updateMemoMutation = useMutation({
    mutationFn: ({ id, data }) => memoApi.patchMemo(id, data), // 使用 patchMemo 进行部分更新
    onMutate: async (updatedMemo) => {
      await queryClient.cancelQueries({ queryKey: ['memos'] });
      const previousMemosData = queryClient.getQueryData(['memos']);

      queryClient.setQueryData(['memos'], (oldData) => {
        if (!oldData || !oldData.results) {
          return oldData;
        }
        const newResults = oldData.results.map((memo) =>
          memo.id === updatedMemo.id ? { ...memo, ...updatedMemo.data } : memo
        );
        return { ...oldData, results: newResults };
      });

      return { previousMemosData };
    },
    // 如果 mutation 失败，使用 onErorr 回滚
    onError: (err, updatedMemo, context) => {
      queryClient.setQueryData(['memos'], context.previousMemosData);
    },
    // 总是在 mutation 结束后重新获取数据，以确保数据同步
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['memos'] });
    },
  });

  // 删除备忘录
  const deleteMemoMutation = useMutation({
    mutationFn: memoApi.deleteMemo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memos'] });
    },
  });

  return {
    memos: memosQuery.data || [],
    isLoading: memosQuery.isLoading,
    error: memosQuery.error,
    createMemo: createMemoMutation.mutate,
    updateMemo: updateMemoMutation.mutate,
    deleteMemo: deleteMemoMutation.mutate,
    queryClient,
  };
};