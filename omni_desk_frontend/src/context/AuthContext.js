import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { jwtDecode } from 'jwt-decode';
import apiClient from '../api/apiClient';
import pageConfigApi from '../api/pageConfigApi';

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
      console.error('Failed to fetch page configurations:', error);
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
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${access}`;
            try {
              const res = await apiClient.get('/users/me/');
              const storedPermissions = JSON.parse(localStorage.getItem('userPermissions') || sessionStorage.getItem('userPermissions') || '[]');
              const permissions = storedPermissions || [];
              const userDataWithPermissions = { ...res.data, permissions };
              setUser(userDataWithPermissions);
              setIsGuest(false);
              await fetchPageConfigs();
            } catch (error) {
              console.error('Failed to fetch user data:', error);
              localStorage.removeItem('authTokens');
              delete apiClient.defaults.headers.common['Authorization'];
            }
          }
        } catch (error) {
          console.error('Error parsing authTokens:', error);
          localStorage.removeItem('authTokens');
        }
      }
      setIsInitializing(false);
    };

    initializeAuth();
  }, [fetchPageConfigs]);

  const login = async (username, password, rememberMe = false) => {
    try {
      const res = await apiClient.post('/auth/login/', {
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
        localStorage.setItem('userPermissions', JSON.stringify(res.data.permissions || []));
      } else {
        sessionStorage.setItem('authTokens', JSON.stringify(authTokens));
        sessionStorage.setItem('userPermissions', JSON.stringify(res.data.permissions || []));
      }
      
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${res.data.access}`;
      
      const userRes = await apiClient.get('/users/me/');
      const permissions = res.data.permissions || [];
      const userData = { ...userRes.data, permissions };

      setUser(userData);
      setIsGuest(false);
      await fetchPageConfigs();
      
      console.log('Login successful - auth state updated:', {
        user: userData,
        isAuthenticated: true,
        isGuest: false
      });
      
      return { 
        success: true,
        redirectTo: '/'
      };
    } catch (err) {
      console.error('Login failed:', err);
      return { success: false, error: err.response?.data?.detail || '登录失败' };
    }
  };

  const register = async (username, password) => {
    try {
      const res = await apiClient.post('/auth/registration/', { 
        username,
        password
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
  };

  const logout = () => {
    localStorage.removeItem('authTokens');
    sessionStorage.removeItem('authTokens');
    delete apiClient.defaults.headers.common['Authorization'];
    setUser(null);
    setIsGuest(false);
    setPageConfigs([]);
    window.location.href = '/';
  };

  const loginAsGuest = async () => {
    try {
      localStorage.removeItem('authTokens');
      sessionStorage.removeItem('authTokens');
      delete apiClient.defaults.headers.common['Authorization'];
      setUser(null);
      setIsGuest(true);
      setPageConfigs([]);
      await new Promise(resolve => setTimeout(resolve, 50));
      return { success: true };
    } catch (error) {
      console.error('Guest login failed:', error);
      return { success: false, error: '游客登录失败' };
    }
  };

  const hasPermission = (permission) => {
    if (!user || !user.permissions) {
      return false;
    }
    return user.permissions.includes(permission);
  };

  const isPageVisible = useCallback((pagePath) => {
    // 管理员始终可见所有页面
    if (user && user.role === 'admin') {
      return true;
    }

    // 确保 pageConfigs 是一个数组
    if (!Array.isArray(pageConfigs)) {
      return true; // 如果 pageConfigs 不是数组，默认可见以避免错误
    }

    const config = pageConfigs.find(pc => pc.page_path === pagePath);
    if (config) {
      // 如果配置为对非管理员隐藏，且当前用户不是管理员，则隐藏
      if (config.is_hidden_for_non_admin && user && user.role !== 'admin') {
        return false;
      }
    }
    // 默认可见，或者没有特殊配置的页面也可见
    return true;
  }, [user, pageConfigs]);

  const value = {
    user,
    isAuthenticated: !!user,
    isGuest,
    isInitializing,
    login,
    logout,
    register,
    loginAsGuest,
    hasPermission,
    pageConfigs,
    isPageVisible,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
