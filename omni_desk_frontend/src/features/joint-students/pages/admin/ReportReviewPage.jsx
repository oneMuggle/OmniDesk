import { useState } from 'react';
import {
  Table,
  Tag,
  Button,
  Space,
  Modal,
  Input,
  message,
  Select,
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listReports, approveReport, rejectReport } from '../../api/reports';

const STATUS_LABEL = {
  draft: { label: '草稿', color: 'default' },
  submitted: { label: '待审核', color: 'gold' },
  approved: { label: '已通过', color: 'green' },
  rejected: { label: '已驳回', color: 'red' },
};

export default function ReportReviewPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState('submitted');
  const [rejectModal, setRejectModal] = useState({ open: false, id: null, comment: '' });

  const { data, isLoading } = useQuery({
    queryKey: ['joint-students', 'reports', status],
    queryFn: () => listReports(status ? { status } : {}),
  });

  const rows = data?.data?.results || data?.data || [];

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['joint-students', 'reports'] });
  };

  const approveMutation = useMutation({
    mutationFn: (id) => approveReport(id),
    onSuccess: () => {
      message.success('已通过');
      invalidate();
    },
    onError: () => message.error('操作失败'),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, comment }) => rejectReport(id, comment),
    onSuccess: () => {
      message.success('已驳回');
      invalidate();
      setRejectModal({ open: false, id: null, comment: '' });
    },
    onError: () => message.error('驳回失败'),
  });

  const columns = [
    { title: '联培生', dataIndex: 'student_name' },
    { title: '学号', dataIndex: 'student_id' },
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
      title: '操作',
      key: 'actions',
      render: (_, r) =>
        r.status === 'submitted' ? (
          <Space>
            <Button
              type="primary"
              size="small"
              onClick={() => approveMutation.mutate(r.id)}
            >
              通过
            </Button>
            <Button
              danger
              size="small"
              onClick={() => setRejectModal({ open: true, id: r.id, comment: '' })}
            >
              驳回
            </Button>
          </Space>
        ) : (
          <Tag color={STATUS_LABEL[r.status]?.color || 'default'}>
            {STATUS_LABEL[r.status]?.label || r.status}
          </Tag>
        ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>月度报告审核</h2>
      <Space style={{ marginBottom: 16 }}>
        <Select
          value={status}
          onChange={setStatus}
          options={[
            { value: '', label: '全部' },
            { value: 'draft', label: '草稿' },
            { value: 'submitted', label: '待审核' },
            { value: 'approved', label: '已通过' },
            { value: 'rejected', label: '已驳回' },
          ]}
          style={{ width: 140 }}
        />
      </Space>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={Array.isArray(rows) ? rows : []}
        columns={columns}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }}
      />
      <Modal
        title="驳回报告"
        open={rejectModal.open}
        onCancel={() => setRejectModal({ open: false, id: null, comment: '' })}
        onOk={() => {
          const trimmed = rejectModal.comment.trim();
          if (!trimmed) {
            message.warning('请填写驳回理由');
            return;
          }
          rejectMutation.mutate({ id: rejectModal.id, comment: trimmed });
        }}
        confirmLoading={rejectMutation.isPending}
        okText="确认驳回"
        cancelText="取消"
      >
        <Input.TextArea
          rows={4}
          value={rejectModal.comment}
          onChange={(e) =>
            setRejectModal((prev) => ({ ...prev, comment: e.target.value }))
          }
          placeholder="请填写驳回理由"
        />
      </Modal>
    </div>
  );
}
