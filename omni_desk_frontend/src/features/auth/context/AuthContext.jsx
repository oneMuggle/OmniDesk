import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import apiClient from '../../../shared/api/axiosConfig';
import pageConfigApi from '../../../shared/api/pageConfigApi';
import { logger } from '../../../shared/utils/logger';

export const AuthContext = createContext({
  user: null,
  isAuthenticated: false,
  isGuest: false,
  hasPermission: () => false,
  login: () => Promise.resolve({ success: false }),
  logout: () => {},
  register: () => Promise.resolve({ success: false }),
  loginAsGuest: () => {},
  pageConfigs: [],
  isPageVisible: () => true,
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isGuest, setIsGuest] = useState(false);
  const [pageConfigs, setPageConfigs] = useState([]);

  const fetchPageConfigs = useCallback(async () => {
    try {
      const response = await pageConfigApi.getAllPageConfigs();
      setPageConfigs(response.data);
    } catch (error) {
      logger.error('Failed to fetch page configurations:', error);
      setPageConfigs([]);
    }
  }, []);

  useEffect(() => {
    const initializeAuth = async () => {
      const storedTokens = localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens');
      if (storedTokens) {
        try {
          const { access } = JSON.parse(storedTokens);
          if (access) {
            try {
              const res = await apiClient.get('users/me/');
              const isGuestUser = res.data.username?.startsWith('guest_');
              setUser(res.data);
              setIsGuest(isGuestUser);
              if (!isGuestUser) {
                await fetchPageConfigs();
              }
            } catch (error) {
              logger.error('Failed to fetch user data:', error);
              localStorage.removeItem('authTokens');
              sessionStorage.removeItem('authTokens');
            }
          }
        } catch (error) {
          logger.error('Error parsing authTokens:', error);
          localStorage.removeItem('authTokens');
          sessionStorage.removeItem('authTokens');
        }
      }
      setIsInitializing(false);
    };

    initializeAuth();
  }, [fetchPageConfigs]);

  const login = useCallback(async (username, password, rememberMe = false) => {
    try {
      const res = await apiClient.post('auth/login/', {
        username,
        password,
        remember_me: rememberMe
      });
      const authTokens = {
        access: res.data.access,
        refresh: res.data.refresh
      };

      if (rememberMe) {
        localStorage.setItem('authTokens', JSON.stringify(authTokens));
      } else {
        sessionStorage.setItem('authTokens', JSON.stringify(authTokens));
      }

      if (res.data.permissions) {
        if (rememberMe) {
          localStorage.setItem('userPermissions', JSON.stringify(res.data.permissions));
        } else {
          sessionStorage.setItem('userPermissions', JSON.stringify(res.data.permissions));
        }
      }

      const userRes = await apiClient.get('users/me/');
      setUser(userRes.data);
      setIsGuest(false);
      await fetchPageConfigs();

      return {
        success: true,
        redirectTo: '/'
      };
    } catch (err) {
      logger.error('Login failed:', err);
      return { success: false, error: err.response?.data?.detail || '登录失败' };
    }
  }, [fetchPageConfigs]);

  const register = useCallback(async ({ username, password, password_confirmation }) => {
    try {
      const res = await apiClient.post('auth/registration/', {
        username,
        password,
        password_confirmation
      });

      if (res.status === 201) {
        return {
          success: true,
          data: res.data,
          message: '注册成功，请登录'
        };
      }
      return {
        success: false,
        errors: res.data || { non_field_errors: ['注册失败'] }
      };
    } catch (err) {
      return {
        success: false,
        errors: err.response?.data || { non_field_errors: ['服务器错误'] }
      };
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('authTokens');
    sessionStorage.removeItem('authTokens');
    localStorage.removeItem('userPermissions');
    sessionStorage.removeItem('userPermissions');
    setUser(null);
    setIsGuest(false);
    setPageConfigs([]);
    window.location.href = isGuest ? '/login' : '/';
  }, [isGuest]);

  const loginAsGuest = useCallback(async () => {
    try {
      localStorage.removeItem('authTokens');
      sessionStorage.removeItem('authTokens');
      setUser(null);

      const res = await apiClient.post('auth/guest-login/', {});
      const authTokens = {
        access: res.data.access,
        refresh: res.data.refresh,
      };
      sessionStorage.setItem('authTokens', JSON.stringify(authTokens));

      const userRes = await apiClient.get('users/me/');
      const guestUser = { ...userRes.data, is_guest: true };
      setUser(guestUser);
      setIsGuest(true);
      await fetchPageConfigs();

      return { success: true };
    } catch (error) {
      logger.error('Guest login failed:', error);
      setIsGuest(true);
      return { success: false, error: '游客登录失败' };
    }
  }, [fetchPageConfigs]);

  const hasPermission = useCallback((requiredPermissions) => {
    // 1. Superusers have all permissions.
    if (user?.is_superuser) {
      return true;
    }

    // 2. If no specific permissions are required, grant access.
    if (!requiredPermissions || requiredPermissions.length === 0) {
      return true;
    }

    // 3. Check if the user has at least one of the required permissions.
    if (user?.permissions) {
      const userPermissions = Array.isArray(user.permissions) ? user.permissions : [user.permissions];
      const required = Array.isArray(requiredPermissions) ? requiredPermissions : [requiredPermissions];
      
      return required.some(p => userPermissions.includes(p));
    }

    // 4. Guest users can access pages whose required permissions match their group permissions.
    if (isGuest && user?.permissions) {
      const userPermissions = Array.isArray(user.permissions) ? user.permissions : [user.permissions];
      const required = Array.isArray(requiredPermissions) ? requiredPermissions : [requiredPermissions];
      return required.some(p => userPermissions.includes(p));
    }

    // 5. Deny access if no user permissions found.
    return false;
  }, [user, isGuest]);

  const value = useMemo(() => ({
    user,
    setUser,
    isAuthenticated: !!user,
    isGuest,
    isInitializing,
    login,
    logout,
    register,
    loginAsGuest,
    hasPermission,
    pageConfigs,
  }), [user, isGuest, isInitializing, login, logout, register, loginAsGuest, hasPermission, pageConfigs]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export function useAuth() {
  return useContext(AuthContext);
}
