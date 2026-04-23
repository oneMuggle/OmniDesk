import axios from 'axios';

const instance = axios.create({
    baseURL: '/api/',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    }
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) prom.reject(error);
        else prom.resolve(token);
    });
    failedQueue = [];
};

// Attach access token to every request
instance.interceptors.request.use(config => {
    const authTokens = JSON.parse(localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}');
    const token = authTokens.access;
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, error => {
    return Promise.reject(error);
});

// Auto-refresh access token on 401
instance.interceptors.response.use(
    response => response,
    async error => {
        const originalRequest = error.config;

        if (error.response?.status !== 401 || originalRequest._retry) {
            return Promise.reject(error);
        }

        if (isRefreshing) {
            return new Promise((resolve, reject) => {
                failedQueue.push({ resolve, reject });
            })
                .then(token => {
                    originalRequest.headers.Authorization = `Bearer ${token}`;
                    return instance(originalRequest);
                })
                .catch(err => Promise.reject(err));
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

            const { data } = await axios.post(
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
            window.location.href = '/login?redirect=' +
                encodeURIComponent(window.location.pathname);
            return Promise.reject(refreshError);
        } finally {
            isRefreshing = false;
        }
    }
);

export default instance;
