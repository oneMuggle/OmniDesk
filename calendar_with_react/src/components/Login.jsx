import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Login.css';

const Login = () => {
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isRegistering) {
      if (password !== confirmPassword) {
        setError('密码和确认密码不一致');
        return;
      }
    }

    if (!username || !password) {
      setError(isRegistering ? '请填写所有字段' : '请输入用户名和密码');
      return;
    }
    
    try {
      setIsLoading(true);
      setError('');

      if (isRegistering) {
        const result = await register(username, password);
        if (result.error) throw new Error(result.error);
        navigate('/');
      } else {
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 1000));
        if (username === 'admin' && password === 'admin123') {
          login({ username });
          navigate('/');
        } else {
          throw new Error('无效的凭证');
        }
      }
    } catch (err) {
      setError(err.message || '登录失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <form onSubmit={handleSubmit}>
        <h2>{isRegistering ? '注册' : '登录'}</h2>
        {error && <div className="error-message">{error}</div>}
        <div className="form-group">
          <label>用户名</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label>密码</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        
        {isRegistering && (
          <div className="form-group">
            <label>确认密码</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
        )}
        
        <button type="submit" disabled={isLoading}>
          {isLoading ? (isRegistering ? '注册中...' : '登录中...') : (isRegistering ? '注册' : '登录')}
        </button>
        
        <p className="toggle-mode">
          {isRegistering ? '已有账号？' : '没有账号？'}
          <button 
            type="button"
            onClick={() => setIsRegistering(!isRegistering)}
            className="link-button"
          >
            {isRegistering ? '立即登录' : '立即注册'}
          </button>
        </p>
      </form>
    </div>
  );
};

export default Login;
