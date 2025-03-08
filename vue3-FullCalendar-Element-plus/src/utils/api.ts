import axios from 'axios';

export interface UserData {
  username: string;
  password: string;
  email?: string;
  phone?: string;
}

export interface Credentials {
  username: string;
  password: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  phone: string;
}

const apiClient = axios.create({
    baseURL: 'http://localhost:8000/api',
    headers: {
        'Content-Type': 'application/json',
    }
});

apiClient.interceptors.request.use(config => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export default apiClient;

export const authService = {
    async register(userData: UserData) {
        return apiClient.post('/register', userData);
    },

    async login(credentials: Credentials) {
        return apiClient.post('/login', credentials);
    },

    async getCurrentUser(): Promise<User> {
        return apiClient.get('/user');
    },

    logout() {
        localStorage.removeItem('access_token');
        delete apiClient.defaults.headers.common['Authorization'];
    }
};
