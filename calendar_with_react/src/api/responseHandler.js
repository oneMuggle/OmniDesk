export const handleResponse = (response) => {
  if (response.status >= 200 && response.status < 300) {
    return response.data;
  }
  const error = new Error(response.statusText);
  error.response = response;
  throw error;
};

export const handleError = (error) => {
  console.error('API call failed:', {
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

  // 确保错误对象有必要的属性
  const enhancedError = new Error(error.message || 'API请求失败');
  enhancedError.name = error.name || 'ApiError';
  enhancedError.stack = error.stack;
  enhancedError.response = error.response;
  enhancedError.config = error.config;
  enhancedError.details = error.details || {};

  // 特殊处理 map is not a function 错误
  if (error.message && error.message.includes('map is not a function')) {
    enhancedError.message = `数据处理失败: ${error.message}`;
    enhancedError.details.dataType = typeof error.response?.data;
    enhancedError.details.originalData = error.response?.data;
  }

  throw enhancedError;
};
