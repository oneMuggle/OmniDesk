/**
 * 账户绑定页 (paperless-ngx 集成)
 *
 * 查看当前绑定状态、绑定或解绑 paperless 账号。
 * 后端接口:`/api/paperless/bind/`
 *   GET  → 获取当前绑定信息
 *   POST → 绑定 (body: { username, password })
 *   DELETE → 解绑
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card, Form, Input, Button, Alert, Descriptions, Space, message, Popconfirm, Spin, Typography,
} from 'antd';
import {
  LinkOutlined, DisconnectOutlined, UserOutlined, LockOutlined,
} from '@ant-design/icons';
import axiosInstance from '../../../shared/api/axiosConfig';
import PaperlessHealthBanner from '../components/PaperlessHealthBanner';

const { Title, Text } = Typography;

const fetchBinding = async () => {
  const { data } = await axiosInstance.get('/paperless/bind/');
  return data;
};

const bindAccount = async (values) => {
  const { data } = await axiosInstance.post('/paperless/bind/', values);
  return data;
};

const unbindAccount = async () => {
  await axiosInstance.delete('/paperless/bind/');
};

export default function AccountBindingPage() {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: binding, isLoading } = useQuery({
    queryKey: ['paperless-binding'],
    queryFn: fetchBinding,
    retry: false,
  });

  const bindMutation = useMutation({
    mutationFn: bindAccount,
    onSuccess: () => {
      message.success('绑定成功');
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['paperless-binding'] });
    },
    onError: (error) => {
      const msg = error.response?.data?.detail
        || error.response?.data?.message
        || error.message
        || '绑定失败';
      message.error(msg);
    },
  });

  const unbindMutation = useMutation({
    mutationFn: unbindAccount,
    onSuccess: () => {
      message.success('已解绑');
      queryClient.invalidateQueries({ queryKey: ['paperless-binding'] });
    },
    onError: (error) => {
      const msg = error.response?.data?.detail
        || error.response?.data?.message
        || error.message
        || '解绑失败';
      message.error(msg);
    },
  });

  const isBound = !!binding?.bound;

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>账户绑定</h2>

      <PaperlessHealthBanner />

      <Spin spinning={isLoading}>
        {isBound ? (
          <Card
            title={
              <Space>
                <LinkOutlined />
                <span>已绑定</span>
              </Space>
            }
            extra={
              <Popconfirm
                title="确认解绑?"
                description="解绑后无法同步新文档到 paperless,已有文档不受影响。"
                onConfirm={() => unbindMutation.mutate()}
                okText="解绑"
                cancelText="取消"
              >
                <Button
                  danger
                  icon={<DisconnectOutlined />}
                  loading={unbindMutation.isPending}
                >
                  解绑
                </Button>
              </Popconfirm>
            }
            style={{ maxWidth: 720 }}
          >
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="用户名">
                {binding.username || '—'}
              </Descriptions.Item>
              <Descriptions.Item label="绑定时间">
                {binding.bound_at
                  ? new Date(binding.bound_at).toLocaleString('zh-CN')
                  : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Text type="success">● 已连接</Text>
              </Descriptions.Item>
            </Descriptions>
          </Card>
        ) : (
          <Card
            title={
              <Space>
                <LinkOutlined />
                <span>绑定 paperless 账号</span>
              </Space>
            }
            style={{ maxWidth: 720 }}
          >
            <Alert
              type="info"
              showIcon
              message="绑定说明"
              description="绑定后,上传的文档将自动同步到 paperless 文档库,同步过程在后台进行。"
              style={{ marginBottom: 16 }}
            />

            <Form
              form={form}
              layout="vertical"
              onFinish={(values) => bindMutation.mutate(values)}
            >
              <Form.Item
                label="paperless 用户名"
                name="username"
                rules={[{ required: true, message: '请输入用户名' }]}
              >
                <Input
                  prefix={<UserOutlined />}
                  placeholder="paperless 账号用户名"
                  autoComplete="username"
                />
              </Form.Item>

              <Form.Item
                label="paperless 密码"
                name="password"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password
                  prefix={<LockOutlined />}
                  placeholder="paperless 账号密码"
                  autoComplete="current-password"
                />
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<LinkOutlined />}
                  loading={bindMutation.isPending}
                >
                  绑定
                </Button>
              </Form.Item>
            </Form>
          </Card>
        )}
      </Spin>
    </div>
  );
}
