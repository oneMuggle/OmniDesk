/**
 * axiosConfig /api/ 双前缀兜底守卫测试
 *
 * 直接对真实的 axios 实例发请求(通过 mock adapter 屏蔽网络),
 * 验证以 '/api/' 开头的 url 会被请求拦截器拒绝。
 */
import instance from '../axiosConfig';

const GUARD_ERROR_MESSAGE = 'Do not include /api/ in apiClient calls';

describe('axiosConfig /api/ 双前缀守卫', () => {
    let mockAdapter: jest.Mock;

    beforeEach(() => {
        localStorage.clear();
        sessionStorage.clear();
        mockAdapter = jest.fn().mockResolvedValue({
            data: { ok: true },
            status: 200,
            statusText: 'OK',
            headers: {},
            request: {},
        });
    });

    it('拒绝以 /api/ 开头的 url(防止与 baseURL 叠加成 /api/api/)', async () => {
        await expect(
            instance.request({ url: '/api/events/', adapter: mockAdapter })
        ).rejects.toThrow(GUARD_ERROR_MESSAGE);

        expect(mockAdapter).not.toHaveBeenCalled();
    });

    it('apiClient.get("/api/xxx") 写法同样被拒绝', async () => {
        await expect(
            instance.get('/api/dify-apps/', { adapter: mockAdapter })
        ).rejects.toThrow(GUARD_ERROR_MESSAGE);

        expect(mockAdapter).not.toHaveBeenCalled();
    });

    it('相对路径 url 正常放行', async () => {
        const response = await instance.request({
            url: 'events/',
            adapter: mockAdapter,
        });

        expect(mockAdapter).toHaveBeenCalledTimes(1);
        expect(response.status).toBe(200);
        expect(response.data).toEqual({ ok: true });
    });

    it('baseURL 保持 /api/ 前缀(相对路径拼接后仍是正确的 /api/xxx)', () => {
        expect(instance.defaults.baseURL).toBe('/api/');
    });

    it('非 /api/ 开头的绝对路径 url 不受守卫影响', async () => {
        await instance.request({
            url: 'http://example.com/api/data',
            adapter: mockAdapter,
        });

        expect(mockAdapter).toHaveBeenCalledTimes(1);
    });

    it('localStorage 非法 JSON 时清理并回退到合法 sessionStorage token', async () => {
        localStorage.setItem('authTokens', '{invalid-json');
        sessionStorage.setItem('authTokens', JSON.stringify({ access: 'session-token' }));

        await instance.request({ url: 'events/', adapter: mockAdapter });

        expect(localStorage.getItem('authTokens')).toBeNull();
        expect(mockAdapter.mock.calls[0][0].headers.Authorization).toBe('Bearer session-token');
    });

    it('localStorage 合法时优先于 sessionStorage', async () => {
        localStorage.setItem('authTokens', JSON.stringify({ access: 'local-token' }));
        sessionStorage.setItem('authTokens', JSON.stringify({ access: 'session-token' }));

        await instance.request({ url: 'events/', adapter: mockAdapter });

        expect(mockAdapter.mock.calls[0][0].headers.Authorization).toBe('Bearer local-token');
    });

    it('两个 storage 都是非法 JSON 时不发送 Authorization', async () => {
        localStorage.setItem('authTokens', '{invalid-local');
        sessionStorage.setItem('authTokens', '{invalid-session');

        await instance.request({ url: 'events/', adapter: mockAdapter });

        expect(localStorage.getItem('authTokens')).toBeNull();
        expect(sessionStorage.getItem('authTokens')).toBeNull();
        expect(mockAdapter.mock.calls[0][0].headers.Authorization).toBeUndefined();
    });

    it('login 请求不发送已保存的 Authorization', async () => {
        localStorage.setItem('authTokens', JSON.stringify({ access: 'secret-access' }));

        await instance.request({ url: 'auth/login/', adapter: mockAdapter });

        expect(mockAdapter.mock.calls[0][0].headers.Authorization).toBeUndefined();
    });
});
