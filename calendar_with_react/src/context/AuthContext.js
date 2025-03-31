import React, { createContext, useContext, useState, useEffect } from 'react';
import { ApiProvider } from './ApiProvider.jsx';
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  },
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken'
});

// 添加请求拦截器
apiClient.interceptors.request.use(config => {
  console.log('发起请求:', config.method.toUpperCase(), config.url);
  return config;
});

// 添加响应拦截器
apiClient.interceptors.response.use(
  response => {
    console.log('收到响应:', response.status, response.data);
    return response;
  },
  error => {
    console.error('请求错误:', error.message);
    return Promise.reject(error);
  }
);

export const AuthContext = createContext({
  user: null,
  login: () => Promise.resolve({ success: false }),
  logout: () => {},
  register: () => Promise.resolve({ success: false })
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  // 初始化时检查本地存储的token
  useEffect(() => {
    const storedTokens = localStorage.getItem('authTokens');
    if (storedTokens) {
      try {
        const { access } = JSON.parse(storedTokens);
        if (access) {
          apiClient.defaults.headers.common['Authorization'] = `Bearer ${access}`;
          // 获取用户信息
          apiClient.get('/api/users/me/')
            .then(res => setUser(res.data))
            .catch(() => {
              localStorage.removeItem('authTokens');
              delete apiClient.defaults.headers.common['Authorization'];
            });
        }
      } catch (error) {
        console.error('Error parsing authTokens:', error);
        localStorage.removeItem('authTokens');
      }
    }
  }, []);

  const login = async (username, password) => {
    try {
      const res = await apiClient.post('/api/auth/login/', { username, password });
      const authTokens = {
        access: res.data.access,
        refresh: res.data.refresh
      };
      localStorage.setItem('authTokens', JSON.stringify(authTokens));
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${res.data.access}`;
      
      const userRes = await apiClient.get('/api/users/me/');
      setUser(userRes.data);
      window.location.href = '/';
      return { success: true };
    } catch (err) {
      console.error('Login failed:', err);
      return { success: false, error: err.response?.data?.detail || '登录失败' };
    }
  };

  const register = async (username, password) => {
    try {
      const res = await apiClient.post('/api/auth/registration/', { 
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
    delete apiClient.defaults.headers.common['Authorization'];
    setUser(null);
    window.location.href = '/login';
  };

  const value = {
    user,
    login,
    logout,
    register
  };

  return (
    <AuthContext.Provider value={value}>
      <ApiProvider>
        {children}
      </ApiProvider>
    </AuthContext.Provider>
  );
}




export function useAuth() {
  return useContext(AuthContext);
}
