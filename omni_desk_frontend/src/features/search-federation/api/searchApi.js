import axiosInstance from '../../../shared/api/axiosConfig';

/**
 * 调用后端统一联邦搜索接口。
 *
 * @param {string} query - 用户输入的搜索关键词
 * @returns {Promise<{results: Array, degraded: boolean}>}
 */
export const unifiedSearch = async (query) => {
  const { data } = await axiosInstance.post('/search/unified/', { query });
  return data;
};
