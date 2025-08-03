import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';
import apiClient from '../api/apiClient';

export const AuthContext = createContext({
  user: null,
  isAuthenticated: false,
  isGuest: false,
  hasPermission: () => false,
  login: () => Promise.resolve({ success: false }),
  logout: () => {},
  register: () => Promise.resolve({ success: false }),
  loginAsGuest: () => {}
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isGuest, setIsGuest] = useState(false);
  
  useEffect(() => {
    const storedTokens = localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens');
    if (storedTokens) {
      try {
        const { access } = JSON.parse(storedTokens);
        if (access) {
          const decodedToken = jwtDecode(access);
          const storedPermissions = JSON.parse(localStorage.getItem('userPermissions') || sessionStorage.getItem('userPermissions') || '[]');
          const permissions = storedPermissions || [];

          apiClient.defaults.headers.common['Authorization'] = `Bearer ${access}`;
          apiClient.get('/users/me/')
            .then(res => {
              const userDataWithPermissions = { ...res.data, permissions };
              setUser(userDataWithPermissions);
              setIsInitializing(false);
              setIsGuest(false);
            })
            .catch(() => {
              localStorage.removeItem('authTokens');
              delete apiClient.defaults.headers.common['Authorization'];
              setIsInitializing(false);
            });
        } else {
          setIsInitializing(false);
        }
      } catch (error) {
        console.error('Error parsing authTokens:', error);
        localStorage.removeItem('authTokens');
        setIsInitializing(false);
      }
    } else {
      setIsInitializing(false);
    }
  }, []);

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
      const permissions = res.data.permissions || []; // 从登录API的原始响应中获取权限
      const userData = { ...userRes.data, permissions };

      setUser(userData);
      setIsGuest(false);
      
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
    window.location.href = '/';
  };

  const loginAsGuest = async () => {
    try {
      localStorage.removeItem('authTokens');
      sessionStorage.removeItem('authTokens');
      delete apiClient.defaults.headers.common['Authorization'];
      setUser(null);
      setIsGuest(true);
      // 添加微小延迟确保状态更新
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

  const value = {
    user,
    isAuthenticated: !!user,
    isGuest,
    isInitializing,
    login,
    logout,
    register,
    loginAsGuest,
    hasPermission
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
