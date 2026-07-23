import { setupDemoInterceptor } from '../demoInterceptor';
import { MOCK_DIFY_APPS, MOCK_RAGFLOW_CONFIGS } from '../demoMocks';
import axios from 'axios';

// Mock localStorage for test environment
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: jest.fn((key) => store[key] || null),
    setItem: jest.fn((key, value) => { store[key] = value; }),
    removeItem: jest.fn((key) => { delete store[key]; }),
    clear: jest.fn(() => { store = {}; }),
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock, writable: true });

// Replace axios.defaults.adapter with a controllable mock for fallback tests.
// In jsdom there's no real XHR adapter, so we must mock it.
const fakeNetworkResponse = { data: 'NETWORK', status: 999, headers: {}, config: {}, request: {} };
const fakeNetworkAdapter = jest.fn().mockResolvedValue(fakeNetworkResponse);
axios.defaults.adapter = fakeNetworkAdapter;

describe('setupDemoInterceptor', () => {
  let instance;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock.clear();
    // Each test gets a fresh instance whose adapter starts as the (mocked) real adapter
    instance = { defaults: { adapter: fakeNetworkAdapter } };
  });

  it('替换 instance.defaults.adapter', () => {
    const original = instance.defaults.adapter;
    setupDemoInterceptor(instance, () => false);
    expect(instance.defaults.adapter).not.toBe(original);
    expect(typeof instance.defaults.adapter).toBe('function');
  });

  it('不会递归调用自己（HMR 安全）', () => {
    // First call: installs demoAdapter
    setupDemoInterceptor(instance, () => false);
    const firstAdapter = instance.defaults.adapter;

    // Second call: instance.defaults.adapter is now demoAdapter. If we
    // captured instance.defaults.adapter as fallback, this would recurse.
    setupDemoInterceptor(instance, () => false);
    const secondAdapter = instance.defaults.adapter;

    expect(secondAdapter).not.toBe(firstAdapter); // fresh function
    // Now turn demo off and call the new adapter — must reach the real
    // network adapter, NOT the previous demoAdapter.
    return secondAdapter({ method: 'get', url: 'x' }).then(() => {
      expect(fakeNetworkAdapter).toHaveBeenCalled();
    });
  });

  describe('demo 模式开启时 (localStorage flag = "true")', () => {
    beforeEach(() => {
      localStorageMock.getItem.mockImplementation((key) =>
        key === 'omnidesk:demo-mode' ? 'true' : null
      );
      setupDemoInterceptor(instance, () => false);
    });

    async function call(config) {
      return instance.defaults.adapter(config);
    }

    it('GET /dify-apps/ 返回 mock 列表', async () => {
      const r = await call({ method: 'get', url: 'dify-apps/' });
      expect(r.data).toEqual({ results: MOCK_DIFY_APPS });
      expect(r.status).toBe(200);
      expect(fakeNetworkAdapter).not.toHaveBeenCalled();
    });

    it('GET /api/dify-apps/ 返回 mock 列表（绝对路径）', async () => {
      const r = await call({ method: 'get', url: '/api/dify-apps/' });
      expect(r.data).toEqual({ results: MOCK_DIFY_APPS });
    });

    it('GET /dify-apps/:id/ 返回 mock 详情', async () => {
      const r = await call({ method: 'get', url: 'dify-apps/1/' });
      expect(r.data).toEqual(MOCK_DIFY_APPS[0]);
    });

    it('GET 不存在的 id 返回 404', async () => {
      const r = await call({ method: 'get', url: 'dify-apps/999/' });
      expect(r.status).toBe(404);
    });

    it('POST /dify-apps/ 创建', async () => {
      const r = await call({ method: 'post', url: 'dify-apps/', data: { name: 'Test' } });
      expect(r.status).toBe(201);
      expect(r.data).toMatchObject({ name: 'Test', id: expect.any(Number) });
    });

    it('PUT /dify-apps/:id/ 更新', async () => {
      const r = await call({ method: 'put', url: 'dify-apps/1/', data: { name: 'Updated' } });
      expect(r.status).toBe(200);
      expect(r.data).toMatchObject({ id: 1, name: 'Updated' });
    });

    it('DELETE /dify-apps/:id/ 删除', async () => {
      const r = await call({ method: 'delete', url: 'dify-apps/1/' });
      expect(r.status).toBe(204);
    });

    it('GET /ragflow-service/configs/ 返回 mock 列表', async () => {
      const r = await call({ method: 'get', url: 'ragflow-service/configs/' });
      expect(r.data).toEqual({ results: MOCK_RAGFLOW_CONFIGS });
    });

    it('POST /ragflow-service/configs/:id/query/ 返回 mock 问答', async () => {
      const r = await call({
        method: 'post',
        url: 'ragflow-service/configs/1/query/',
        data: { question: '年假有多少天？' },
      });
      expect(r.data).toMatchObject({
        answer: expect.stringContaining('员工手册'),
        conversation_id: expect.stringMatching(/^demo-conv-/),
      });
    });

    it('未匹配的 URL 走默认 adapter', async () => {
      const config = { method: 'get', url: 'other-endpoint/' };
      const r = await instance.defaults.adapter(config);
      expect(fakeNetworkAdapter).toHaveBeenCalledWith(config);
      expect(r.data).toBe('NETWORK');
    });

    it('返回的 mock 响应结构完整（statusText/headers/request 都有）', async () => {
      const r = await call({ method: 'get', url: 'dify-apps/' });
      expect(r).toMatchObject({
        data: expect.any(Object),
        status: 200,
        statusText: 'OK',
        headers: expect.any(Object),
        config: expect.any(Object),
        request: expect.any(Object),
      });
    });
  });

  describe('demo 模式关闭时 (localStorage flag = null)', () => {
    beforeEach(() => {
      localStorageMock.getItem.mockReturnValue(null);
      setupDemoInterceptor(instance, () => false);
    });

    it('所有请求透传到默认 adapter', async () => {
      const config = { method: 'get', url: 'dify-apps/' };
      const r = await instance.defaults.adapter(config);
      expect(fakeNetworkAdapter).toHaveBeenCalledWith(config);
      expect(r.data).toBe('NETWORK');
    });
  });
});
