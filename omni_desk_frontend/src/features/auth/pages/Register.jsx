import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import './Login.css';

const Register = () => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    const { register } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (values) => {
        const { username, password, confirmPassword } = values;

        if (password !== confirmPassword) {
            message.error('密码和确认密码不一致');
            return;
        }

        try {
            setLoading(true);
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
            message.success('注册成功，请登录');
            navigate('/login', {
                state: { registeredUsername: username.trim() }
            });
        } catch (err) {
            message.error(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-brand">
                    <div className="brand-logo">OmniDesk</div>
                    <div className="brand-subtitle">创建您的账号</div>
                </div>

                <Form
                    form={form}
                    name="register"
                    onFinish={handleSubmit}
                    layout="vertical"
                    size="large"
                >
                    <Form.Item
                        name="username"
                        rules={[
                            { required: true, message: '请输入用户名' },
                        ]}
                    >
                        <Input
                            prefix={<UserOutlined />}
                            placeholder="用户名"
                            size="large"
                        />
                    </Form.Item>

                    <Form.Item
                        name="password"
                        rules={[
                            { required: true, message: '请输入密码' },
                            { min: 6, message: '密码至少6个字符' },
                        ]}
                    >
                        <Input.Password
                            prefix={<LockOutlined />}
                            placeholder="密码"
                            size="large"
                        />
                    </Form.Item>

                    <Form.Item
                        name="confirmPassword"
                        dependencies={['password']}
                        rules={[
                            { required: true, message: '请确认密码' },
                            ({ getFieldValue }) => ({
                                validator(_, value) {
                                    if (!value || getFieldValue('password') === value) {
                                        return Promise.resolve();
                                    }
                                    return Promise.reject(new Error('密码不一致'));
                                },
                            }),
                        ]}
                    >
                        <Input.Password
                            prefix={<LockOutlined />}
                            placeholder="确认密码"
                            size="large"
                        />
                    </Form.Item>

                    <Form.Item style={{ marginBottom: 16 }}>
                        <Button
                            type="primary"
                            htmlType="submit"
                            loading={loading}
                            block
                            size="large"
                            className="login-button"
                        >
                            注册
                        </Button>
                    </Form.Item>
                </Form>

                <div className="login-footer">
                    <span>已有账号？</span>
                    <Link to="/login">立即登录</Link>
                </div>
            </div>
        </div>
    );
};

export default Register;
