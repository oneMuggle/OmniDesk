import axios from 'axios';

/**
 * 联培生模块 API 客户端工厂
 *
 * 与 `src/shared/api/axiosConfig.js` 行为一致:baseURL + JWT 拦截 + 401 跳登录。
 * 这里独立成实例,便于在 jest 中 mock / 替换 baseURL。
 *
 * @param {object} [instance=axios] 可注入的 axios 根对象(测试用)
 * @returns {object} 配置好的 axios 实例
 */
export const createJointStudentsClient = (instance = axios) => {
  const client = instance.create({
    baseURL: '/api/joint-students/',
    timeout: 30000,
  });

  client.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (r) => r,
    (err) => {
      if (err.response?.status === 401) {
        localStorage.removeItem('access_token');
        window.location.href = '/login';
        // 401 拦截后不再 reject(已跳转登录),保持 settled 状态
      }
      return Promise.reject(err);
    }
  );

  return client;
};

export default createJointStudentsClient();
