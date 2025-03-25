import React, { createContext, useContext, useState, useEffect } from 'react';
import { ApiProvider } from './ApiProvider.jsx';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL
});

export const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  // 初始化时检查本地存储的token
  useEffect(() => {
    const token = localStorage.getItem('access');
    if (token) {
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      // 获取用户信息
      apiClient.get('/users/me/')
        .then(res => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('access');
          localStorage.removeItem('refresh');
          delete apiClient.defaults.headers.common['Authorization'];
        });
    }
  }, []);

  const login = async (username, password) => {
    try {
      const res = await apiClient.post('/auth/token/', { username, password });
      localStorage.setItem('access', res.data.access);
      localStorage.setItem('refresh', res.data.refresh);
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${res.data.access}`;
      
      const userRes = await apiClient.get('/users/me/');
      setUser(userRes.data);
      navigate('/');
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data?.detail || '登录失败' };
    }
  };

  const register = async (username, password, email = '') => {
    try {
      await apiClient.post('/auth/register/', { 
        username,
        password,
        email
      });
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data || '注册失败' };
    }
  };

  const logout = () => {
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
    delete apiClient.defaults.headers.common['Authorization'];
    setUser(null);
    navigate('/login');
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
