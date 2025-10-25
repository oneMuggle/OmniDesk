import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import memoApi from '../api/memoApi';

export const useMemoData = () => {
  const queryClient = useQueryClient();

  // 获取所有备忘录
  const { data, isLoading, error } = useQuery({
    queryKey: ['memos'],
    queryFn: memoApi.getAllMemos,
    select: (data) => data.results, // 提取results数组
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
    onMutate: async (newMemo) => {
      await queryClient.cancelQueries(['memos']);
      const previousMemos = queryClient.getQueryData(['memos']);

      queryClient.setQueryData(['memos'], (old) => {
        const oldMemos = Array.isArray(old) ? old : old?.results || [];
        return oldMemos.map((memo) =>
          memo.id === newMemo.id ? { ...memo, ...newMemo } : memo
        );
      });

      return { previousMemos };
    },
    // 如果 mutation 失败，使用 onErorr 回滚
    onError: (err, newMemo, context) => {
      queryClient.setQueryData(['memos'], context.previousMemos);
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
    memos: data || [],
    isLoading,
    error,
    createMemo: createMemoMutation.mutate,
    updateMemo: updateMemoMutation.mutate,
    deleteMemo: deleteMemoMutation.mutate,
    queryClient,
  };
};