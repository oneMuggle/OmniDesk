import axios from 'axios';

const instance = axios.create({
    baseURL: '/api/',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    }
});

// You can add interceptors here if needed, for example, to attach auth tokens.
instance.interceptors.request.use(config => {
    const authTokens = JSON.parse(localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}');
    const token = authTokens.access; // Correctly extract the access token

    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, error => {
    return Promise.reject(error);
});

export default instance;