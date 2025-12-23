import { useState } from 'react';
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

        if (password !== confirmPassword) {
            setError('密码和确认密码不一致');
            return;
        }

        try {
            setIsLoading(true);
            setError('');
            const result = await register({
                username: username.trim(),
                password: password.trim(),
                password_confirmation: confirmPassword.trim()
            });
            if (!result.success) {
                const errorMessage = result.errors?.non_field_errors?.[0]
                    || result.errors?.detail
                    || Object.values(result.errors || {})[0]?.[0]
                    || '注册失败';
                throw new Error(errorMessage);
            }
            // 注册成功后跳转到登录页面并传递用户名
            navigate('/login', { 
                state: { registeredUsername: username.trim() }
            });
        } catch (err) {
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
                <div className="form-group">
                    <label htmlFor="confirmPassword">确认密码</label>
                    <input
                        id="confirmPassword"
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="确认密码"
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
