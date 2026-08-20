import apiClient from '../../../shared/api/apiClient';

/**
 * 联培生模块 API 客户端。
 *
 * 复用全局 Axios 实例,统一使用 VITE_API_BASE_URL、authTokens、JWT refresh
 * queue 和 X-Request-ID,避免模块客户端与项目认证约定分叉。
 */
export const createJointStudentsClient = (instance = apiClient) => instance;

export default apiClient;
