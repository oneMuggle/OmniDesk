import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from 'antd';
import './Login.css';

const Login = () => {
  const location = useLocation();
  const [username, setUsername] = useState(location.state?.registeredUsername || '');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const { login, loginAsGuest } = useAuth();
  const navigate = useNavigate();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    console.log('handleSubmit triggered');
    e.preventDefault();
    if (!username || !password) {
      setError('请输入用户名和密码');
      return;
    }
    
    try {
      setIsLoading(true);
      setError('');

      const result = await login(username.trim(), password.trim(), rememberMe);
      if (!result.success) throw new Error(result.error);
      
      console.log('Login successful, waiting for state update...');
      // 添加微小延迟确保状态完全更新
      await new Promise(resolve => setTimeout(resolve, 100));
      
      console.log('Redirecting after login...');
      navigate(result.redirectTo || '/');
    } catch (err) {
      setError(err.message || '登录失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <form onSubmit={handleSubmit}>
        <h2>登录</h2>
        {error && <div className="error-message">{error}</div>}
        <div className="form-group">
          <label htmlFor="username">用户名</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="用户名"
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">密码</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="密码"
            required
          />
        </div>

        <div className="form-group remember-me">
          <label>
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
            />
            记住我
          </label>
        </div>
        
        <Button
          type="primary"
          htmlType="submit"
          loading={isLoading}
          disabled={isLoading}
          block
          className="login-button"
        >
          {isLoading ? '登录中...' : '登录'}
        </Button>
        
        <p className="toggle-mode">
          没有账号？
          <Link to="/register" className="link-button">
            立即注册
          </Link>
        </p>
        <Button
          type="default"
          onClick={async () => {
            try {
              setIsLoading(true);
              setError('');
              const result = await loginAsGuest();
              if (result.success) {
                navigate('/');
              } else {
                setError(result.error || '游客登录失败');
              }
            } catch (err) {
              setError('游客登录失败，请重试');
            } finally {
              setIsLoading(false);
            }
          }}
          loading={isLoading}
          disabled={isLoading}
          style={{ marginTop: '16px', width: '100%' }}
          className="login-button"
        >
          {isLoading ? '正在进入...' : '以游客身份访问'}
        </Button>
      </form>
    </div>
  );
};

export default Login;
