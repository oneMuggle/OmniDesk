import { useState } from 'react';
import { Tag, Button, Space, Modal, Input, message, Select } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listStipends, lockStipend } from '../../api/stipends';
import { listCycles } from '../../api/cycles';
import GradeBadge from '../../components/GradeBadge';
import DataTable from '../../../../shared/components/DataTable';

const STATUS_LABEL = {
  pending: { label: '待复核', color: 'gold' },
  locked: { label: '已锁定', color: 'green' },
};

export default function StipendReviewPage() {
  const queryClient = useQueryClient();
  const [cycleId, setCycleId] = useState();
  const [status, setStatus] = useState('');
  const [lockModal, setLockModal] = useState({ open: false, id: null, notes: '' });

  const { data: cyclesData } = useQuery({
    queryKey: ['joint-students', 'cycles'],
    queryFn: () => listCycles(),
  });
  const cycles = cyclesData?.data?.results || cyclesData?.data || [];

  const { data, isLoading } = useQuery({
    queryKey: ['joint-students', 'stipends', { cycleId, status }],
    queryFn: () => {
      const params = {};
      if (cycleId) params.cycle = cycleId;
      if (status) params.status = status;
      return listStipends(params);
    },
  });

  const rows = data?.data?.results || data?.data || [];

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['joint-students', 'stipends'] });
  };

  const lockMutation = useMutation({
    mutationFn: ({ id, notes }) => lockStipend(id, notes),
    onSuccess: () => {
      message.success('已锁定');
      invalidate();
      setLockModal({ open: false, id: null, notes: '' });
    },
    onError: () => message.error('锁定失败'),
  });

  const columns = [
    { title: '联培生', dataIndex: 'student_name' },
    { title: '学号', dataIndex: 'student_id' },
    { title: '排名', dataIndex: 'rank_in_cycle' },
    {
      title: '档次',
      dataIndex: 'grade',
      render: (g) => <GradeBadge grade={g} />,
    },
    {
      title: '出勤比',
      dataIndex: 'attendance_ratio',
      render: (v) => `${(parseFloat(v) * 100).toFixed(0)}%`,
    },
    {
      title: '最终金额',
      dataIndex: 'final_amount',
      render: (v) => `${parseFloat(v).toFixed(2)} 元`,
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
        r.status === 'pending' ? (
          <Button
            type="primary"
            size="small"
            onClick={() => setLockModal({ open: true, id: r.id, notes: '' })}
          >
            复核通过
          </Button>
        ) : null,
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>补助复核</h2>
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          placeholder="按批次"
          allowClear
          style={{ width: 200 }}
          value={cycleId}
          onChange={setCycleId}
          options={cycles.map((c) => ({
            value: c.id,
            label: `${c.year}-${String(c.month).padStart(2, '0')}`,
          }))}
        />
        <Select
          placeholder="状态"
          allowClear
          value={status}
          onChange={setStatus}
          options={[
            { value: 'pending', label: '待复核' },
            { value: 'locked', label: '已锁定' },
          ]}
          style={{ width: 140 }}
        />
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
        title="复核并锁定"
        open={lockModal.open}
        onCancel={() => setLockModal({ open: false, id: null, notes: '' })}
        onOk={() => lockMutation.mutate({ id: lockModal.id, notes: lockModal.notes })}
        confirmLoading={lockMutation.isPending}
        okText="确认锁定"
        cancelText="取消"
      >
        <p>确认后联培生将看到该补助记录。是否填写复核备注？</p>
        <Input.TextArea
          rows={3}
          value={lockModal.notes}
          onChange={(e) =>
            setLockModal((prev) => ({ ...prev, notes: e.target.value }))
          }
          placeholder="可选：复核备注"
        />
      </Modal>
    </div>
  );
}
