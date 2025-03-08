import { defineStore } from 'pinia';
import { authService } from '../utils/api';
import type { Credentials, UserData, User } from '../utils/api';

export const useAuthStore = defineStore('auth', {
    state: () => ({
        user: null as User | null,
        isAuthenticated: !!localStorage.getItem('access_token'),
    }),
    actions: {
        async login(credentials: Credentials) {
            const response = await authService.login(credentials);
            this.isAuthenticated = true;
            this.user = await authService.getCurrentUser();
        },
        async register(userData: UserData) {
            await authService.register(userData);
            this.isAuthenticated = true;
            this.user = await authService.getCurrentUser();
        },
        async getCurrentUser() {
            this.user = await authService.getCurrentUser();
            return this.user;
        },
        logout() {
            authService.logout();
            this.isAuthenticated = false;
            this.user = null;
        },
    },
});
