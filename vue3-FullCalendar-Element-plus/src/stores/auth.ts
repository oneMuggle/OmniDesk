import { defineStore } from 'pinia';
import apiClient from '../utils/api';

export const useAuthStore = defineStore('auth', {
    state: () => ({
        accessToken: localStorage.getItem('access_token') || '',
        refreshToken: localStorage.getItem('refresh_token') || '',
    }),
    actions: {
        async login(credentials: { username: string, password: string }) {
            const response = await apiClient.post('/token/', credentials);
            this.accessToken = response.data.access;
            this.refreshToken = response.data.refresh;
            localStorage.setItem('access_token', this.accessToken);
            localStorage.setItem('refresh_token', this.refreshToken);
        },
        logout() {
            this.accessToken = '';
            this.refreshToken = '';
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
        },
        async refreshToken() {
            const response = await apiClient.post('/token/refresh/', {
                refresh: this.refreshToken,
            });
            this.accessToken = response.data.access;
            localStorage.setItem('access_token', this.accessToken);
        },
    },
});
