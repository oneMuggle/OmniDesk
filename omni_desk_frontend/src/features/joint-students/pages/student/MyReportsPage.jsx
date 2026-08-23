import { useState, useEffect } from 'react';
import {
  Tag,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  message,
  Space,
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listReports, submitReport, createReport, updateReport } from '../../api/reports';
import DataTable from '../../../../shared/components/DataTable';

const STATUS_LABEL = {
  draft: { label: '草稿', color: 'default' },
  submitted: { label: '待审核', color: 'gold' },
  approved: { label: '已通过', color: 'green' },
  rejected: { label: '已驳回', color: 'red' },
};

const now = () => {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
};

export default function MyReportsPage() {
  const queryClient = useQueryClient();
  const [editModal, setEditModal] = useState({ open: false, record: null });
  const [form] = Form.useForm();

  const today = now();

  const { data, isLoading } = useQuery({
    queryKey: ['joint-students', 'my-reports'],
    queryFn: () => listReports(),
  });
  const rows = data?.data?.results || data?.data || [];

  const hasThisMonthSubmitted = rows.some(
    (r) => r.year === today.year && r.month === today.month && r.status === 'approved'
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['joint-students', 'my-reports'] });
  };

  const submitMutation = useMutation({
    mutationFn: (id) => submitReport(id),
    onSuccess: () => {
      message.success('已提交');
      invalidate();
    },
    onError: () => message.error('提交失败'),
  });

  const saveMutation = useMutation({
    mutationFn: (values) => {
      const payload = {
        year: values.year,
        month: values.month,
        work_progress: values.work_progress,
        work_highlights: values.work_highlights,
        attendance_days_actual: values.attendance_days_actual,
        attendance_days_expected: values.attendance_days_expected ?? 22,
        attendance_notes: values.attendance_notes,
      };
      if (editModal.record?.id) {
        return updateReport(editModal.record.id, payload);
      }
      return createReport(payload);
    },
    onSuccess: () => {
      message.success('已保存');
      invalidate();
      setEditModal({ open: false, record: null });
      form.resetFields();
    },
    onError: () => message.error('保存失败'),
  });

  useEffect(() => {
    if (editModal.open && editModal.record) {
      form.setFieldsValue(editModal.record);
    }
  }, [editModal, form]);

  const openNew = () => {
    form.resetFields();
    form.setFieldsValue({
      year: today.year,
      month: today.month,
      attendance_days_expected: 22,
    });
    setEditModal({ open: true, record: null });
  };

  const columns = [
    { title: '年份', dataIndex: 'year' },
    { title: '月份', dataIndex: 'month' },
    {
      title: '出勤(实/应)',
      key: 'attendance',
      render: (_, r) => `${r.attendance_days_actual} / ${r.attendance_days_expected}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (s) => {
        const cfg = STATUS_LABEL[s] || { label: s, color: 'default' };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '审核意见',
      dataIndex: 'reviewer_comment',
      render: (c) => c || '-',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, r) => (
        <Space>
          <Button
            size="small"
            onClick={() => setEditModal({ open: true, record: r })}
          >
            {r.status === 'rejected' ? '修改' : '查看'}
          </Button>
          {r.status === 'draft' || r.status === 'rejected' ? (
            <Button
              type="primary"
              size="small"
              onClick={() => submitMutation.mutate(r.id)}
            >
              提交
            </Button>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>我的月度报告</h2>
      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          disabled={hasThisMonthSubmitted}
          onClick={openNew}
        >
          {hasThisMonthSubmitted ? '本月已提交' : '新建月度报告'}
        </Button>
      </Space>
      <DataTable
        rowKey="id"
        loading={isLoading}
        dataSource={rows}
        columns={columns}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }}
        showActions={false}
      />
      <Modal
        title={editModal.record?.id ? '编辑月度报告' : '新建月度报告'}
        open={editModal.open}
        onCancel={() => setEditModal({ open: false, record: null })}
        onOk={() => form.submit()}
        confirmLoading={saveMutation.isPending}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Space>
            <Form.Item label="年份" name="year" rules={[{ required: true }]}>
              <InputNumber min={2000} max={2100} />
            </Form.Item>
            <Form.Item label="月份" name="month" rules={[{ required: true }]}>
              <InputNumber min={1} max={12} />
            </Form.Item>
          </Space>
          <Form.Item label="工作进展" name="work_progress" rules={[{ required: true }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item label="工作亮点" name="work_highlights">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Space>
            <Form.Item
              label="实出勤天数"
              name="attendance_days_actual"
              rules={[{ required: true }]}
            >
              <InputNumber min={0} step={0.5} />
            </Form.Item>
            <Form.Item label="应出勤天数" name="attendance_days_expected">
              <InputNumber min={0} step={0.5} />
            </Form.Item>
          </Space>
          <Form.Item label="出勤备注" name="attendance_notes">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
