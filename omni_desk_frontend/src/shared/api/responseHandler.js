import { message } from 'antd'; // 引入 Ant Design 的 message 组件
import { logger } from '../utils/logger';

export const handleResponse = (response) => {
  if (response.status >= 200 && response.status < 300) {
    return response.data;
  }
  const error = new Error(response.statusText);
  error.response = response;
  throw error;
};

export const handleError = (error, showToast = true) => {
  logger.error('API call failed:', {
    message: error.message,
    stack: error.stack,
    config: error.config,
    response: error.response ? {
      status: error.response.status,
      statusText: error.response.statusText,
      data: error.response.data,
      headers: error.response.headers
    } : null,
    request: error.request,
    isAxiosError: error.isAxiosError,
    details: error.details
  });

  let errorMessage = error.message || 'API请求失败';

  // 处理排班日期已存在的错误
  if (error.response?.data?.duty_date) {
    errorMessage = error.response.data.duty_date.join(', ');
  } else if (error.response?.data?.detail) { // 处理 DRF 的 detail 错误
    errorMessage = error.response.data.detail;
  } else if (error.response?.data) { // 尝试从响应数据中获取更具体的错误信息
    errorMessage = JSON.stringify(error.response.data);
  }

  // 特殊处理 map is not a function 错误
  if (errorMessage.includes('map is not a function')) {
    errorMessage = `数据处理失败: ${errorMessage}`;
  }

  if (showToast) message.error(errorMessage); // 显示错误提示

  // 确保错误对象有必要的属性
  const enhancedError = new Error(errorMessage);
  enhancedError.name = error.name || 'ApiError';
  enhancedError.stack = error.stack;
  enhancedError.response = error.response;
  enhancedError.config = error.config;
  enhancedError.details = error.details || {};

  throw enhancedError;
};
