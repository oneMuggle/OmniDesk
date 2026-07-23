import { message } from 'antd'; // 引入 Ant Design 的 message 组件
import { logger } from '../utils/logger';

// 描述 axios / 业务代码可能挂在错误对象上的运行时字段
interface ErrorWithExtras extends Error {
    response?: {
        status: number;
        statusText: string;
        data?: unknown;
        headers?: Record<string, unknown>;
    };
    request?: unknown;
    config?: unknown;
    isAxiosError?: boolean;
    details?: unknown;
}

export const handleResponse = <T = unknown>(response: {
    status: number;
    statusText: string;
    data: T;
}): T => {
    if (response.status >= 200 && response.status < 300) {
        return response.data;
    }
    const error = new Error(response.statusText) as Error & { response: typeof response };
    error.response = response;
    throw error;
};

export const handleError = (error: ErrorWithExtras, showToast = true): never => {
    const err: ErrorWithExtras = error;
    logger.error('API call failed:', {
        message: err.message,
        stack: err.stack,
        config: err.config,
        response: err.response
            ? {
                  status: err.response.status,
                  statusText: err.response.statusText,
                  data: err.response.data,
                  headers: err.response.headers,
              }
            : null,
        request: err.request,
        isAxiosError: err.isAxiosError,
        details: err.details,
    });

    let errorMessage: string = err.message || 'API请求失败';

    const responseData = err.response?.data as Record<string, unknown> | undefined;

    // 处理排班日期已存在的错误
    if (responseData?.duty_date) {
        const dutyDateErrors = responseData.duty_date;
        if (Array.isArray(dutyDateErrors)) {
            errorMessage = dutyDateErrors.join(', ');
        }
    } else if (responseData?.detail) {
        // 处理 DRF 的 detail 错误
        errorMessage = String(responseData.detail);
    } else if (responseData) {
        // 尝试从响应数据中获取更具体的错误信息
        errorMessage = JSON.stringify(responseData);
    }

    // 特殊处理 map is not a function 错误
    if (errorMessage.includes('map is not a function')) {
        errorMessage = `数据处理失败: ${errorMessage}`;
    }

    if (showToast) message.error(errorMessage); // 显示错误提示

    // 确保错误对象有必要的属性
    const enhancedError = new Error(errorMessage) as Error & ErrorWithExtras;
    enhancedError.name = err.name || 'ApiError';
    enhancedError.stack = err.stack;
    enhancedError.response = err.response;
    enhancedError.config = err.config;
    enhancedError.details = err.details || {};

    throw enhancedError;
};
