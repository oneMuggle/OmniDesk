/**
 * 统一 API 错误信息提取(R4-B5)。
 *
 * 后端错误链:response.data.detail → response.data.message → error.message;
 * 全部缺失时回退到调用方给定的 fallback,避免把 undefined 直接渲染到 UI。
 */
export function getApiErrorMessage(error, fallback = '操作失败') {
  return (
    error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || fallback
  );
}