import axiosInstance from '../../../shared/api/axiosConfig.js';

/**
 * 获取集成服务列表
 */
export const fetchIntegrations = async () => {
  const response = await axiosInstance.get('/external/integrations/');
  return response.data;
};

/**
 * 获取 iframe 嵌入 URL
 */
export const getEmbedUrl = async (slug) => {
  const response = await axiosInstance.get(`/external/integrations/${slug}/embed/`);
  return response.data;
};

/**
 * API 代理调用
 */
export const proxyApiCall = async (slug, data) => {
  const response = await axiosInstance.post(`/external/integrations/${slug}/proxy/`, data);
  return response.data;
};

/**
 * 创建集成服务
 */
export const createIntegration = async (data) => {
  const response = await axiosInstance.post('/external/integrations/', data);
  return response.data;
};

/**
 * 更新集成服务
 */
export const updateIntegration = async (slug, data) => {
  const response = await axiosInstance.put(`/external/integrations/${slug}/`, data);
  return response.data;
};

/**
 * 删除集成服务
 */
export const deleteIntegration = async (slug) => {
  await axiosInstance.delete(`/external/integrations/${slug}/`);
};
