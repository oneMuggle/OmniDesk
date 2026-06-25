/**
 * Demo mode axios request interceptor
 * Intercepts specific URL patterns in demo mode and returns mock data.
 * Unmatched requests pass through transparently.
 */

import { MOCK_DIFY_APPS, MOCK_RAGFLOW_CONFIGS, pickMockResponse } from './demoMocks';
import { logger } from '../utils/logger';

/**
 * 设置 demo 模式拦截器
 * @param {import('axios').AxiosInstance} axiosInstance - axios 实例
 * @param {() => boolean} getIsDemoMode - 获取当前 demo 模式的函数
 */
export function setupDemoInterceptor(axiosInstance, getIsDemoMode) {
  axiosInstance.interceptors.request.use(async (config) => {
    if (!getIsDemoMode()) {
      return config;
    }

    const { method, url } = config;
    const lowerMethod = (method || 'get').toLowerCase();

    // GET /api/dify-apps/
    if (lowerMethod === 'get' && /^\/api\/dify-apps\/?$/.test(url)) {
      logger.debug('[demo] intercepted GET /api/dify-apps/');
      return Promise.resolve({ data: { results: MOCK_DIFY_APPS }, status: 200, config });
    }

    // GET /api/dify-apps/:id/
    const difyDetailMatch = url.match(/^\/api\/dify-apps\/(\d+)\/?$/);
    if (lowerMethod === 'get' && difyDetailMatch) {
      const id = parseInt(difyDetailMatch[1], 10);
      const app = MOCK_DIFY_APPS.find((a) => a.id === id);
      if (app) {
        logger.debug('[demo] intercepted GET /api/dify-apps/:id/', { id });
        return Promise.resolve({ data: app, status: 200, config });
      }
      return Promise.resolve({ data: { detail: 'Not found' }, status: 404, config });
    }

    // POST /api/dify-apps/
    if (lowerMethod === 'post' && /^\/api\/dify-apps\/?$/.test(url)) {
      const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
      const newApp = {
        ...payload,
        id: Date.now(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      logger.debug('[demo] intercepted POST /api/dify-apps/', { newApp });
      return Promise.resolve({ data: newApp, status: 201, config });
    }

    // PUT /api/dify-apps/:id/
    const difyUpdateMatch = url.match(/^\/api\/dify-apps\/(\d+)\/?$/);
    if (lowerMethod === 'put' && difyUpdateMatch) {
      const id = parseInt(difyUpdateMatch[1], 10);
      const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
      const existing = MOCK_DIFY_APPS.find((a) => a.id === id);
      const updated = { ...existing, ...payload, id };
      logger.debug('[demo] intercepted PUT /api/dify-apps/:id/', { id, updated });
      return Promise.resolve({ data: updated, status: 200, config });
    }

    // DELETE /api/dify-apps/:id/
    const difyDeleteMatch = url.match(/^\/api\/dify-apps\/(\d+)\/?$/);
    if (lowerMethod === 'delete' && difyDeleteMatch) {
      const id = parseInt(difyDeleteMatch[1], 10);
      logger.debug('[demo] intercepted DELETE /api/dify-apps/:id/', { id });
      return Promise.resolve({ data: {}, status: 204, config });
    }

    // GET /api/ragflow-service/configs/
    if (lowerMethod === 'get' && /^\/api\/ragflow-service\/configs\/?$/.test(url)) {
      logger.debug('[demo] intercepted GET /api/ragflow-service/configs/');
      return Promise.resolve({ data: { results: MOCK_RAGFLOW_CONFIGS }, status: 200, config });
    }

    // POST /api/ragflow-service/configs/:id/query/
    const ragflowQueryMatch = url.match(/^\/api\/ragflow-service\/configs\/(\d+)\/query\/?$/);
    if (lowerMethod === 'post' && ragflowQueryMatch) {
      const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
      const answer = pickMockResponse(payload.question);
      logger.debug('[demo] intercepted POST /api/ragflow-service/configs/:id/query/', {
        question: payload.question,
      });
      return Promise.resolve({
        data: {
          answer,
          conversation_id: `demo-conv-${Date.now()}`,
        },
        status: 200,
        config,
      });
    }

    // 未匹配，透传
    return config;
  });
}
