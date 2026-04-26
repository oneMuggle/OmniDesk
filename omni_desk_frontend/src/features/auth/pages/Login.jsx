import { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Form, Input, Button, Checkbox, Card, message } from 'antd';
import './Login.css';

const Login = () => {
  const location = useLocation();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const { login, loginAsGuest } = useAuth();
  const navigate = useNavigate();

  const initialUsername = location.state?.registeredUsername || '';
  if (initialUsername && form) {
    form.setFieldsValue({ username: initialUsername });
  }

  const handleSubmit = async (values) => {
    const { username, password, remember } = values;

    if (!username || !password) {
      message.error('请输入用户名和密码');
      return;
    }

    try {
      setLoading(true);
      const result = await login(username.trim(), password.trim(), remember);
      if (!result.success) throw new Error(result.error);
      message.success('登录成功');
      navigate(result.redirectTo || '/');
    } catch (err) {
      message.error(err.message || '登录失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleGuestLogin = async () => {
    try {
      setLoading(true);
      const result = await loginAsGuest();
      if (result.success) {
        message.success('欢迎访问');
        navigate('/');
      } else {
        message.error(result.error || '游客登录失败');
      }
    } catch (err) {
      message.error('游客登录失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <Card className="login-card" title="登录">
        <Form
          form={form}
          name="login"
          onFinish={handleSubmit}
          layout="vertical"
          initialValues={{ username: initialUsername }}
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="用户名" size="large" />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password placeholder="密码" size="large" />
          </Form.Item>

          <Form.Item name="remember" valuePropName="checked">
            <Checkbox>记住我</Checkbox>
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              登录
            </Button>
          </Form.Item>
        </Form>

        <div className="login-footer">
          <span>没有账号？</span>
          <Link to="/register">立即注册</Link>
        </div>

        <Button block size="large" onClick={handleGuestLogin} loading={loading}>
          以游客身份访问
        </Button>
      </Card>
    </div>
  );
};

export default Login;