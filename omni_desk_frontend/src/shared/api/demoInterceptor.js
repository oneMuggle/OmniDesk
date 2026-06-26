/**
 * Demo mode axios adapter
 *
 * Replaces axios's default XHR/HTTP adapter with one that returns mock
 * data for whitelisted URLs when demo mode is enabled. Unmatched
 * requests fall through to the real adapter.
 *
 * Why an adapter (not a request interceptor)?
 * axios v1.x request interceptors CANNOT short-circuit the request —
 * dispatchRequest is always called after the interceptor chain. We
 * have to intercept at the adapter level, which is the only axios hook
 * that controls whether the network call happens.
 *
 * Demo state is read from localStorage ('omnidesk:demo-mode') so the
 * adapter and React Context never drift out of sync under Vite HMR.
 */

import { MOCK_DIFY_APPS, MOCK_RAGFLOW_CONFIGS, pickMockResponse } from './demoMocks';
import { logger } from '../utils/logger';
import axios from 'axios';

const STORAGE_KEY = 'omnidesk:demo-mode';

/**
 * Read demo mode state directly from localStorage.
 */
function isDemoModeEnabled() {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

/**
 * Normalize URL: strip optional /api/ prefix and ensure leading /.
 */
function normalizePath(url) {
  if (!url) return '';
  let path = url.replace(/^\/api\//, '/').replace(/^api\//, '/');
  if (!path.startsWith('/')) {
    path = '/' + path;
  }
  return path;
}

/**
 * Match the request against demo URL patterns and return the mock
 * response payload, or null if it should pass through.
 */
function getMockPayload(config) {
  const method = (config.method || 'get').toLowerCase();
  const path = normalizePath(config.url);

  // GET /dify-apps/
  if (method === 'get' && /^\/dify-apps\/?$/.test(path)) {
    return { status: 200, data: { results: MOCK_DIFY_APPS } };
  }

  // GET /dify-apps/:id/
  const difyDetailMatch = path.match(/^\/dify-apps\/(\d+)\/?$/);
  if (method === 'get' && difyDetailMatch) {
    const id = parseInt(difyDetailMatch[1], 10);
    const app = MOCK_DIFY_APPS.find((a) => a.id === id);
    if (app) return { status: 200, data: app };
    return { status: 404, data: { detail: 'Not found' } };
  }

  // POST /dify-apps/
  if (method === 'post' && /^\/dify-apps\/?$/.test(path)) {
    const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
    const newApp = {
      ...payload,
      id: Date.now(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return { status: 201, data: newApp };
  }

  // PUT /dify-apps/:id/
  const difyUpdateMatch = path.match(/^\/dify-apps\/(\d+)\/?$/);
  if (method === 'put' && difyUpdateMatch) {
    const id = parseInt(difyUpdateMatch[1], 10);
    const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
    const existing = MOCK_DIFY_APPS.find((a) => a.id === id);
    return { status: 200, data: { ...existing, ...payload, id } };
  }

  // DELETE /dify-apps/:id/
  const difyDeleteMatch = path.match(/^\/dify-apps\/(\d+)\/?$/);
  if (method === 'delete' && difyDeleteMatch) {
    return { status: 204, data: {} };
  }

  // GET /ragflow-service/configs/
  if (method === 'get' && /^\/ragflow-service\/configs\/?$/.test(path)) {
    return { status: 200, data: { results: MOCK_RAGFLOW_CONFIGS } };
  }

  // POST /ragflow-service/configs/:id/query/
  const ragflowQueryMatch = path.match(/^\/ragflow-service\/configs\/(\d+)\/query\/?$/);
  if (method === 'post' && ragflowQueryMatch) {
    const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
    return {
      status: 200,
      data: {
        answer: pickMockResponse(payload.question),
        conversation_id: `demo-conv-${Date.now()}`,
      },
    };
  }

  return null;
}

/**
 * Resolve the real (network) adapter once, so demoAdapter can delegate
 * non-mocked requests to it without recursing into itself.
 *
 * Note: `axios.defaults.adapter` is NOT a function in axios v1.x —
 * it's an *array* of adapters (xhr + http). We must call
 * `axios.getAdapter(adapters)` to obtain a callable function.
 */
function resolveRealAdapter() {
  const adapters = axios.defaults.adapter;
  if (typeof adapters === 'function') {
    return adapters;
  }
  if (Array.isArray(adapters) && adapters.length > 0) {
    return axios.getAdapter(adapters);
  }
  // Last-resort fallback (older axios or unusual builds)
  if (typeof axios.getAdapter === 'function' && axios.adapters) {
    return axios.getAdapter(axios.adapters);
  }
  throw new Error(
    '[demoInterceptor] Cannot resolve a real network adapter from axios; ' +
      'demo mode cannot fall through to real requests.'
  );
}

/**
 * Set up the demo mode adapter. We always fall through to the original
 * XHR adapter (resolved from axios) so that calling this function
 * multiple times (e.g. after Vite HMR) does not recurse into ourselves.
 *
 * @param {import('axios').AxiosInstance} axiosInstance
 * @param {() => boolean} [_getIsDemoMode] - 已废弃：现在从 localStorage 读取，保留参数仅为向后兼容
 */
export function setupDemoInterceptor(axiosInstance, _getIsDemoMode) {
  const realAdapter = resolveRealAdapter();

  axiosInstance.defaults.adapter = function demoAdapter(config) {
    if (!isDemoModeEnabled()) {
      return realAdapter(config);
    }

    const mock = getMockPayload(config);
    if (!mock) {
      // Not a demo URL — pass through to real adapter
      return realAdapter(config);
    }

    logger.debug('[demo] intercepted', { method: config.method, url: config.url });

    // Build the response in the shape axios expects. This mirrors
    // what the default adapter produces on a successful response.
    return Promise.resolve({
      data: mock.data,
      status: mock.status,
      statusText: mock.status >= 200 && mock.status < 300 ? 'OK' : 'Error',
      headers: {},
      config,
      request: {},
    });
  };
}
