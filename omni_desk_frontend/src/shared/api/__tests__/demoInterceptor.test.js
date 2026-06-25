import { setupDemoInterceptor } from '../demoInterceptor';
import { MOCK_DIFY_APPS, MOCK_RAGFLOW_CONFIGS } from '../demoMocks';

describe('setupDemoInterceptor', () => {
  let mockAxios;
  let mockInterceptor;
  let getIsDemoMode;

  beforeEach(() => {
    jest.clearAllMocks();
    mockInterceptor = jest.fn();
    mockAxios = {
      interceptors: {
        request: { use: mockInterceptor },
      },
    };
    getIsDemoMode = jest.fn();
  });

  it('注册拦截器', () => {
    setupDemoInterceptor(mockAxios, getIsDemoMode);
    expect(mockInterceptor).toHaveBeenCalledTimes(1);
    expect(typeof mockInterceptor.mock.calls[0][0]).toBe('function');
  });

  describe('demo 模式开启时', () => {
    let interceptorFn;

    beforeEach(() => {
      getIsDemoMode.mockReturnValue(true);
      setupDemoInterceptor(mockAxios, getIsDemoMode);
      interceptorFn = mockInterceptor.mock.calls[0][0];
    });

    it('拦截相对路径 GET /dify-apps/ 返回列表', async () => {
      const config = { method: 'get', url: 'dify-apps/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual({ results: MOCK_DIFY_APPS });
    });

    it('拦截绝对路径 GET /api/dify-apps/ 返回列表', async () => {
      const config = { method: 'get', url: '/api/dify-apps/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual({ results: MOCK_DIFY_APPS });
    });

    it('拦截 GET /dify-apps/:id/ 返回详情', async () => {
      const config = { method: 'get', url: 'dify-apps/1/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual(MOCK_DIFY_APPS[0]);
    });

    it('GET 不存在的 id 返回 404', async () => {
      const config = { method: 'get', url: 'dify-apps/999/' };
      const result = await interceptorFn(config);
      expect(result.status).toBe(404);
    });

    it('拦截 POST /dify-apps/ 创建', async () => {
      const config = { method: 'post', url: 'dify-apps/', data: { name: 'Test' } };
      const result = await interceptorFn(config);
      expect(result.data).toMatchObject({ name: 'Test', id: expect.any(Number) });
    });

    it('拦截 PUT /dify-apps/:id/ 更新', async () => {
      const config = { method: 'put', url: 'dify-apps/1/', data: { name: 'Updated' } };
      const result = await interceptorFn(config);
      expect(result.data).toMatchObject({ id: 1, name: 'Updated' });
    });

    it('拦截 DELETE /dify-apps/:id/ 删除', async () => {
      const config = { method: 'delete', url: 'dify-apps/1/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual({});
    });

    it('拦截 GET /ragflow-service/configs/ 返回列表', async () => {
      const config = { method: 'get', url: 'ragflow-service/configs/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual({ results: MOCK_RAGFLOW_CONFIGS });
    });

    it('拦截 POST /ragflow-service/configs/:id/query/ 返回问答', async () => {
      const config = {
        method: 'post',
        url: 'ragflow-service/configs/1/query/',
        data: { question: '年假有多少天？' },
      };
      const result = await interceptorFn(config);
      expect(result.data).toMatchObject({
        answer: expect.stringContaining('员工手册'),
        conversation_id: expect.stringMatching(/^demo-conv-/),
      });
    });

    it('未匹配的 URL 透传', async () => {
      const config = { method: 'get', url: 'other-endpoint/' };
      const result = await interceptorFn(config);
      expect(result).toBe(config);
    });
  });

  describe('demo 模式关闭时', () => {
    let interceptorFn;

    beforeEach(() => {
      getIsDemoMode.mockReturnValue(false);
      setupDemoInterceptor(mockAxios, getIsDemoMode);
      interceptorFn = mockInterceptor.mock.calls[0][0];
    });

    it('所有请求透传', async () => {
      const config = { method: 'get', url: 'dify-apps/' };
      const result = await interceptorFn(config);
      expect(result).toBe(config);
    });
  });
});
