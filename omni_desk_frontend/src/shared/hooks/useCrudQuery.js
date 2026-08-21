/**
 * useCrudQuery — CRUD 列表页通用 query hook(R5-D6)。
 *
 * 封装 TanStack React Query(v5)的列表页标准用法:
 * - 默认 staleTime 5min、refetchOnWindowFocus false(与 src/index.jsx 的
 *   QueryClient 全局默认一致,显式写出以便脱离全局配置的场景自洽)
 * - fetcher 返回值经 extractResults 收口,DRF 分页({results,count})与
 *   裸数组两种形态统一为数组
 * - 请求失败时自动 message.error 提示(文案可经 options.errorMessage 覆盖,
 *   设为 null 关闭提示);v5 移除了 useQuery 的 onError 回调,故经 useEffect 监听
 * - 返回 { data, isLoading, error, refetch } 及其余 React Query 结果字段
 *
 * 无 JSX,扩展名 .js 即可。
 */
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { message } from 'antd';
import { extractResults } from '../api/responseHandler';

const DEFAULT_STALE_TIME = 1000 * 60 * 5; // 与 index.jsx QueryClient 默认对齐:5 分钟
const DEFAULT_ERROR_MESSAGE = '数据加载失败';

export function useCrudQuery(queryKey, fetcher, options = {}) {
    const {
        errorMessage = DEFAULT_ERROR_MESSAGE,
        staleTime = DEFAULT_STALE_TIME,
        refetchOnWindowFocus = false,
        ...restOptions
    } = options;

    const query = useQuery({
        queryKey,
        queryFn: async () => extractResults(await fetcher()),
        staleTime,
        refetchOnWindowFocus,
        ...restOptions,
    });

    const { isError } = query;
    useEffect(() => {
        if (isError && errorMessage) {
            message.error(errorMessage);
        }
    }, [isError, errorMessage]);

    return query;
}
