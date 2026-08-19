import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { getEnv } from '../utils/env';

const API_BASE_URL = getEnv('VITE_API_BASE_URL', '/api');
// Ensure baseURL ends with /
const baseURL = API_BASE_URL.endsWith('/') ? API_BASE_URL : API_BASE_URL + '/';

interface FailedRequest {
    resolve: (token: string | null) => void;
    reject: (error: unknown) => void;
}

// 自定义 _retry 标记,防止 401 刷新逻辑进入死循环
declare module 'axios' {
    export interface InternalAxiosRequestConfig {
        _retry?: boolean;
    }
}

const instance: AxiosInstance = axios.create({
    baseURL,
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// 兜底守卫:instance 的 baseURL 已包含 /api/ 前缀,调用方再写
// '/api/xxx' 会被拼成 /api/api/xxx 双前缀导致 404。
// 这里在请求发出前直接拒绝,尽早暴露错误用法。
// 注意:window.open / location.href 等浏览器导航不走 axios,不受此守卫影响。
instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        if (config.url?.startsWith('/api/')) {
            return Promise.reject(
                new Error('Do not include /api/ in apiClient calls')
            );
        }
        return config;
    },
    (error: AxiosError) => Promise.reject(error)
);

let isRefreshing = false;
let failedQueue: FailedRequest[] = [];

const processQueue = (error: unknown, token: string | null = null): void => {
    failedQueue.forEach((prom) => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    failedQueue = [];
};

// Attach access token to every request (except login)
instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // 登录请求不应携带 Authorization 头
        const isLoginRequest = config.url?.includes('auth/login');
        if (isLoginRequest) {
            return config;
        }

        const authTokens = JSON.parse(
            localStorage.getItem('authTokens') ||
                sessionStorage.getItem('authTokens') ||
                '{}'
        );
        const token: string | undefined = authTokens.access;
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error: AxiosError) => {
        return Promise.reject(error);
    }
);

// X-Request-ID 链路传播(部署前 P0-2):
// 后端 RequestIdMiddleware 会读入站 X-Request-ID 头,与 Django/Celery/DB 日志串起来。
// 前端拿到响应头后回填,保证同一用户在一次"操作→失败上报"过程中的 rid 一致。
let lastRequestId: string | null = null;

instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // 只在用户主动操作产生请求时回传(非重试刷新)
        if (lastRequestId && !config._retry) {
            config.headers['X-Request-ID'] = lastRequestId;
        }
        return config;
    },
    (error: AxiosError) => Promise.reject(error)
);

// Auto-refresh access token on 401
instance.interceptors.response.use(
    (response) => {
        // 从响应头里抓 X-Request-ID,缓存给下一次请求用
        const rid = response.headers['x-request-id'];
        if (typeof rid === 'string' && rid.length > 0) {
            lastRequestId = rid;
        }
        return response;
    },
    async (error: AxiosError) => {
        const originalRequest = error.config;

        // 登录请求的 401 不应该触发 token 刷新，直接返回错误
        const isLoginRequest = originalRequest?.url?.includes('auth/login');
        if (error.response?.status === 401 && isLoginRequest) {
            return Promise.reject(error);
        }

        if (error.response?.status !== 401 || originalRequest?._retry) {
            return Promise.reject(error);
        }

        if (isRefreshing) {
            return new Promise((resolve, reject) => {
                failedQueue.push({
                    resolve: (token: string | null) => {
                        if (originalRequest && token) {
                            originalRequest.headers.Authorization = `Bearer ${token}`;
                        }
                        resolve(token);
                    },
                    reject,
                });
            })
                .then(() => {
                    if (originalRequest) {
                        return instance(originalRequest);
                    }
                    return Promise.reject(new Error('No original request'));
                })
                .catch((err) => Promise.reject(err));
        }

        if (!originalRequest) {
            return Promise.reject(error);
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
            const tokens = JSON.parse(
                localStorage.getItem('authTokens') ||
                    sessionStorage.getItem('authTokens') ||
                    '{}'
            );

            if (!tokens.refresh) {
                throw new Error('No refresh token');
            }

            const { data } = await axios.post<{ access: string; refresh?: string }>(
                `${instance.defaults.baseURL}auth/token/refresh/`,
                { refresh: tokens.refresh }
            );

            const newTokens = {
                access: data.access,
                refresh: data.refresh || tokens.refresh,
            };

            if (localStorage.getItem('authTokens')) {
                localStorage.setItem('authTokens', JSON.stringify(newTokens));
            }
            if (sessionStorage.getItem('authTokens')) {
                sessionStorage.setItem('authTokens', JSON.stringify(newTokens));
            }

            originalRequest.headers.Authorization = `Bearer ${data.access}`;
            processQueue(null, data.access);

            return instance(originalRequest);
        } catch (refreshError) {
            processQueue(refreshError, null);
            localStorage.removeItem('authTokens');
            sessionStorage.removeItem('authTokens');
            window.location.href =
                '/login?redirect=' +
                encodeURIComponent(window.location.pathname);
            return Promise.reject(refreshError);
        } finally {
            isRefreshing = false;
        }
    }
);

// Demo mode interceptor setup
// The interceptor reads demo state from localStorage directly, so no
// module-level flag is needed here. This avoids HMR-induced state drift
// where multiple axios module copies would each have their own flag.
import { setupDemoInterceptor } from './demoInterceptor';
setupDemoInterceptor(instance, () => {
    try {
        return localStorage.getItem('omnidesk:demo-mode') === 'true';
    } catch {
        return false;
    }
});

/**
 * Set demo mode state. Writes to localStorage (single source of truth
 * shared with DemoContext and the demo interceptor). The function is
 * kept for callers like DemoToggle that want to toggle programmatically.
 */
export function setDemoModeEnabled(enabled: boolean): void {
    try {
        localStorage.setItem('omnidesk:demo-mode', String(enabled));
    } catch {
        // localStorage 不可用，忽略
    }
}

export default instance;
