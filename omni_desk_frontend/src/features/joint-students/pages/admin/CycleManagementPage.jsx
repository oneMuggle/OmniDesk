import { useState } from 'react';
import { Tag, Button, Space, Modal, Form, InputNumber, message } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listCycles, triggerCycle, forceCloseCycle } from '../../api/cycles';
import DataTable from '../../../../shared/components/DataTable';

const STATUS_LABEL = {
  collecting: { label: '收集中', color: 'gold' },
  closed: { label: '已截止', color: 'blue' },
  finalized: { label: '已锁定', color: 'green' },
};

const TRIGGER_LABEL = {
  auto: '自动',
  manual: '手动',
};

export default function CycleManagementPage() {
  const queryClient = useQueryClient();
  const [triggerModal, setTriggerModal] = useState(false);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['joint-students', 'cycles'],
    queryFn: () => listCycles(),
  });

  const rows = data?.data?.results || data?.data || [];

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['joint-students', 'cycles'] });
  };

  const triggerMutation = useMutation({
    mutationFn: (values) => triggerCycle(values),
    onSuccess: () => {
      message.success('已触发批次');
      invalidate();
      setTriggerModal(false);
      form.resetFields();
    },
    onError: () => message.error('触发失败'),
  });

  const forceCloseMutation = useMutation({
    mutationFn: (id) => forceCloseCycle(id),
    onSuccess: () => {
      message.success('已强制截止');
      invalidate();
    },
    onError: () => message.error('操作失败'),
  });

  const columns = [
    { title: '年份', dataIndex: 'year' },
    { title: '月份', dataIndex: 'month' },
    { title: '报告截止', dataIndex: 'cycle_end_date' },
    { title: '打分截止', dataIndex: 'scoring_deadline' },
    {
      title: '状态',
      dataIndex: 'status',
      render: (s) => {
        const cfg = STATUS_LABEL[s] || { label: s, color: 'default' };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '触发方式',
      dataIndex: 'trigger_source',
      render: (s) => TRIGGER_LABEL[s] || s,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, r) =>
        r.status === 'collecting' ? (
          <Button
            danger
            size="small"
            onClick={() =>
              Modal.confirm({
                title: `确认强制截止 ${r.year}-${String(r.month).padStart(2, '0')} 批次?`,
                onOk: () => forceCloseMutation.mutate(r.id),
              })
            }
          >
            强制截止
          </Button>
        ) : null,
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>考核批次管理</h2>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => setTriggerModal(true)}>
          手动触发本月批次
        </Button>
      </Space>
      <DataTable
        rowKey="id"
        loading={isLoading}
        dataSource={Array.isArray(rows) ? rows : []}
        columns={columns}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }}
        showActions={false}
      />
      <Modal
        title="手动触发批次"
        open={triggerModal}
        onCancel={() => setTriggerModal(false)}
        onOk={() => form.submit()}
        confirmLoading={triggerMutation.isPending}
        okText="触发"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => triggerMutation.mutate(values)}
        >
          <Form.Item
            label="年份"
            name="year"
            rules={[{ required: true, message: '请输入年份' }]}
          >
            <InputNumber min={2000} max={2100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            label="月份"
            name="month"
            rules={[{ required: true, message: '请输入月份' }]}
          >
            <InputNumber min={1} max={12} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
