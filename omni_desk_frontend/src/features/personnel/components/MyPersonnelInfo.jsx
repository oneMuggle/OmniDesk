import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Form, Input, Button, Spin, Card, Tooltip, message, Space, Tag } from 'antd';
import { getMyPersonnel, updateMyPersonnel } from '../api/personnelApi';

// 字段级权限定义(详见 plan 文档 §4.1)
// editable=false 的字段从表单排除或 disabled,Tooltip 提示"由 HR 维护"
const FIELD_PERMS = {
  name: { editable: false, source: 'HR' },
  id_card_number: { editable: false, source: 'HR', masked: true },
  date_of_birth: { editable: true },
  phone_number: { editable: true },
  address: { editable: true },
  hire_date: { editable: false, source: 'HR' },
  department: { editable: false, source: 'HR' },
  position: { editable: false, source: 'HR' },
  status: { editable: false, source: 'HR' },
};

const LABELS = {
  name: '姓名',
  phone_number: '联系电话',
  address: '家庭住址',
  date_of_birth: '出生年月',
  department: '部门',
  position: '职位',
  status: '在职状态',
  hire_date: '入职日期',
};

function displayPosition(position) {
  if (!position) return '未设置';
  if (typeof position === 'object') return position.name || '未设置';
  return position;
}

function displayStatus(status) {
  const map = { active: '在职', inactive: '离职' };
  return map[status] || status || '未知';
}

const MyPersonnelInfo = () => {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['myPersonnel'],
    queryFn: getMyPersonnel,
    retry: false,
  });

  const mutation = useMutation({
    mutationFn: (values) => updateMyPersonnel(values),
    onSuccess: () => {
      message.success('个人信息已更新');
      queryClient.invalidateQueries({ queryKey: ['myPersonnel'] });
    },
    onError: (err) => {
      message.error(err?.message || '更新失败,请稍后重试');
    },
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue({
        date_of_birth: data.date_of_birth,
        phone_number: data.phone_number,
        address: data.address,
      });
    }
  }, [data, form]);

  if (isLoading) {
    return (
      <Card title="我的信息">
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin tip="加载中..." />
        </div>
      </Card>
    );
  }

  if (isError) {
    const status = error?.response?.status;
    if (status === 404) {
      return (
        <Card title="我的信息">
          <p>您当前尚未关联人员档案,请联系 HR 处理。</p>
        </Card>
      );
    }
    return (
      <Card title="我的信息">
        <p style={{ color: 'red' }}>加载个人信息失败:{error?.message || '未知错误'}</p>
      </Card>
    );
  }

  const onFinish = (values) => {
    mutation.mutate(values);
  };

  return (
    <Card
      title="我的信息"
      extra={
        data?.status && (
          <Tag color={data.status === 'active' ? 'green' : 'red'}>
            {displayStatus(data.status)}
          </Tag>
        )
      }
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        disabled={mutation.isPending}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* 只读字段:name */}
          <Tooltip
            title={`由 ${FIELD_PERMS.name.source} 维护,如需修改请联系 HR`}
            placement="right"
          >
            <Form.Item label={LABELS.name}>
              <Input value={data?.name || ''} disabled />
            </Form.Item>
          </Tooltip>

          {/* 只读字段:department */}
          <Tooltip
            title={`由 ${FIELD_PERMS.department.source} 维护`}
            placement="right"
          >
            <Form.Item label={LABELS.department}>
              <Input value={data?.department || '未设置'} disabled />
            </Form.Item>
          </Tooltip>

          {/* 只读字段:position */}
          <Tooltip
            title={`由 ${FIELD_PERMS.position.source} 维护`}
            placement="right"
          >
            <Form.Item label={LABELS.position}>
              <Input value={displayPosition(data?.position)} disabled />
            </Form.Item>
          </Tooltip>

          {/* 可写字段:date_of_birth */}
          <Form.Item
            name="date_of_birth"
            label={LABELS.date_of_birth}
            rules={[{ type: 'string', message: '请输入有效日期 YYYY-MM-DD' }]}
          >
            <Input placeholder="1990-01-15" />
          </Form.Item>

          {/* 可写字段:phone_number */}
          <Form.Item
            name="phone_number"
            label={LABELS.phone_number}
            rules={[
              { required: true, message: '请输入联系电话' },
              { pattern: /^\d{11}$/, message: '请输入 11 位手机号' },
            ]}
          >
            <Input placeholder="11 位手机号" maxLength={11} />
          </Form.Item>

          {/* 可写字段:address */}
          <Form.Item name="address" label={LABELS.address}>
            <Input.TextArea rows={2} placeholder="详细住址" />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={mutation.isPending}
            >
              保存
            </Button>
          </Form.Item>
        </Space>
      </Form>
    </Card>
  );
};

export default MyPersonnelInfo;
