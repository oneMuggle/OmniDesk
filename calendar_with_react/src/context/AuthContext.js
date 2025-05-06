import React, { createContext, useContext, useState, useEffect } from 'react';
import { checkPermission } from '../config/permissionConfig';
import apiClient from '../api/apiClient';

export const AuthContext = createContext({
  user: null,
  isAuthenticated: false,
  isGuest: false,
  permissions: {},
  hasPermission: (permission) => false,
  login: () => Promise.resolve({ success: false }),
  logout: () => {},
  register: () => Promise.resolve({ success: false }),
  loginAsGuest: () => {}
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isGuest, setIsGuest] = useState(false);
  const [permissions, setPermissions] = useState({});

  // 初始化时检查本地存储的token
  useEffect(() => {
    const storedTokens = localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens');
    if (storedTokens) {
      try {
        const { access } = JSON.parse(storedTokens);
        if (access) {
          // 统一设置认证头格式
          apiClient.defaults.headers.common['Authorization'] = `Bearer ${access}`;
          // 获取用户信息
          apiClient.get('/users/me/', {
            headers: {
              'Authorization': `Bearer ${access}`
            }
          })
            .then(res => {
              setUser(res.data);
              setPermissions(res.data.permissions || {});
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
      } else {
        sessionStorage.setItem('authTokens', JSON.stringify(authTokens));
      }
      
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${res.data.access}`;
      
      const userRes = await apiClient.get('/users/me/');
      setUser(userRes.data);
      setPermissions(userRes.data.permissions || {});
      setIsGuest(false);
      
      console.log('Login successful - auth state updated:', {
        user: userRes.data,
        isAuthenticated: true,
        isGuest: false
      });
      
      return { 
        success: true,
        redirectTo: '/calendar' 
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
    window.location.href = '/login';
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
    if (!permissions) {
      console.log('权限检查失败: 无权限数据', { permissions, permission });
      return false;
    }
    
    // 处理多种权限数据格式
    let permissionsList = [];
    if (Array.isArray(permissions)) {
      permissionsList = permissions;
    } else if (permissions.permissions && Array.isArray(permissions.permissions)) {
      permissionsList = permissions.permissions;
    } else if (permissions.role === 'superuser') {
      return true; // 超级用户拥有所有权限
    }
    
    // 使用新的权限检查逻辑
    const hasPerm = checkPermission(permissionsList, permission);
    if (!hasPerm) {
      console.warn('权限检查失败:', { 
        permission,
        allPermissions: permissionsList 
      });
    }
    return hasPerm;
  };

  // 权限轮询检查
  useEffect(() => {
    if (!user) return;
    
    const interval = setInterval(async () => {
      try {
        const res = await apiClient.get('/users/me/');
        const newPermissions = res.data.permissions || {};
        if (JSON.stringify(permissions) !== JSON.stringify(newPermissions)) {
          setPermissions(newPermissions);
          console.log('权限已更新:', newPermissions);
        }
      } catch (error) {
        console.error('权限轮询失败:', error);
      }
    }, 5 * 60 * 1000); // 5分钟

    return () => clearInterval(interval);
  }, [user, permissions]);

  const value = {
    user,
    isAuthenticated: !!user,
    isGuest,
    isInitializing,
    permissions,
    hasPermission,
    login,
    logout,
    register,
    loginAsGuest
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
