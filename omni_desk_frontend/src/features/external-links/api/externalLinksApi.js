import axiosInstance from '../../../shared/api/axiosConfig';

/**
 * 获取按分类分组的外链列表
 */
export const fetchExternalLinks = async () => {
  const response = await axiosInstance.get('/external/external-links/');
  return response.data;
};

/**
 * 创建外链
 */
export const createExternalLink = async (data) => {
  const response = await axiosInstance.post('/external/external-links/', data);
  return response.data;
};

/**
 * 更新外链
 */
export const updateExternalLink = async (id, data) => {
  const response = await axiosInstance.put(`/external/external-links/${id}/`, data);
  return response.data;
};

/**
 * 删除外链
 */
export const deleteExternalLink = async (id) => {
  await axiosInstance.delete(`/external/external-links/${id}/`);
};

/**
 * 获取 SSO 跳转链接
 */
export const getSsoToken = async (id) => {
  const response = await axiosInstance.post(`/external/external-links/${id}/sso-token/`);
  return response.data;
};
