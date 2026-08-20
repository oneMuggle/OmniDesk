import { createJointStudentsClient } from './client';

describe('createJointStudentsClient', () => {
  const makeMockAxios = () => ({
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    create: jest.fn(function (config) {
      this.config = config;
      this.interceptors = { request: { use: jest.fn() }, response: { use: jest.fn() } };
      return this;
    }),
  });

  it('createJointStudentsClient 返回带 baseURL /api/joint-students/ 的 axios 实例', () => {
    const mockAxios = makeMockAxios();
    createJointStudentsClient(mockAxios);
    expect(mockAxios.create).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: '/api/joint-students/' })
    );
  });

  it('注册 request 与 response 拦截器', () => {
    const mockAxios = makeMockAxios();
    const client = createJointStudentsClient(mockAxios);
    expect(client.interceptors.request.use).toHaveBeenCalledTimes(1);
    expect(client.interceptors.response.use).toHaveBeenCalledTimes(1);
  });

  it('请求拦截器从 localStorage 读 access_token 并添加 Authorization 头', () => {
    const mockAxios = makeMockAxios();
    const client = createJointStudentsClient(mockAxios);
    const requestInterceptor = client.interceptors.request.use.mock.calls[0][0];

    localStorage.setItem('access_token', 'fake-token');
    const withToken = requestInterceptor({ headers: {} });
    expect(withToken.headers.Authorization).toBe('Bearer fake-token');

    localStorage.clear();
    const noToken = requestInterceptor({ headers: {} });
    expect(noToken.headers.Authorization).toBeUndefined();
  });

  it('response 拦截器 401 → 清 token + 跳 /login', async () => {
    const mockAxios = makeMockAxios();
    const client = createJointStudentsClient(mockAxios);
    const errorInterceptor = client.interceptors.response.use.mock.calls[0][1];

    localStorage.setItem('access_token', 'old');
    const origLocation = window.location;
    delete window.location;
    window.location = { href: '' };

    await expect(
      errorInterceptor({ response: { status: 401 } })
    ).rejects.toBeDefined();
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(window.location.href).toBe('/login');
    window.location = origLocation;
  });

  it('response 拦截器 非 401 → 原样 reject', async () => {
    const mockAxios = makeMockAxios();
    const client = createJointStudentsClient(mockAxios);
    const errorInterceptor = client.interceptors.response.use.mock.calls[0][1];

    const err = new Error('boom');
    err.response = { status: 500 };
    await expect(errorInterceptor(err)).rejects.toBe(err);
  });
});
