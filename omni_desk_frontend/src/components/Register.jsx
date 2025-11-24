import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import './Login.css';

const Register = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const { register } = useAuth();
    const navigate = useNavigate();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        console.log('开始处理注册表单提交'); // 添加调试日志

        if (password !== confirmPassword) {
            console.log('密码验证失败'); // 添加调试日志
            setError('密码和确认密码不一致');
            return;
        }

        try {
            console.log('开始注册流程'); // 添加调试日志
            setIsLoading(true);
            setError('');
            console.log('调用register方法前'); // 添加调试日志
            const result = await register(username.trim(), password.trim(), confirmPassword.trim());
            if (!result.success) {
                const errorMessage = result.errors?.non_field_errors?.[0]
                    || result.errors?.detail
                    || Object.values(result.errors || {})[0]?.[0]
                    || '注册失败';
                throw new Error(errorMessage);
            }
            console.log('register方法返回结果:', result); // 添加调试日志
            // 注册成功后跳转到登录页面并传递用户名
            navigate('/login', { 
                state: { registeredUsername: username.trim() }
            });
        } catch (err) {
            console.error('注册过程中捕获异常:', err); // 添加详细错误日志
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };


    return (
        <div className="login-container">
            <form onSubmit={handleSubmit}>
                <h2>注册</h2>
                {error && <div className="error-message">{error}</div>}
                <div className="form-group">
                    <label>用户名</label>
                    <input
                        type="text"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="用户名"
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
                <div className="form-group">
                    <label>确认密码</label>
                    <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        required
                    />
                </div>
                <button type="submit" disabled={isLoading} className="login-button">
                    {isLoading ? '注册中...' : '注册'}
                </button>
                <p className="toggle-mode">
                    已有账号？<Link to="/login" className="link-button">立即登录</Link>
                </p>
            </form>
        </div>
    );



};





export default Register;
