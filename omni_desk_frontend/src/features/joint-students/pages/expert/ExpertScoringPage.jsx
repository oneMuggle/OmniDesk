import { useState, useMemo } from 'react';
import { Tag, Button, Modal, Form, InputNumber, Input, message, Space } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listReports } from '../../api/reports';
import { listCycles } from '../../api/cycles';
import { listScores, createScore } from '../../api/scores';
import DataTable from '../../../../shared/components/DataTable';

export default function ExpertScoringPage() {
  const queryClient = useQueryClient();
  const [cycleId, setCycleId] = useState();
  const [scoreModal, setScoreModal] = useState({ open: false, record: null });
  const [form] = Form.useForm();

  const { data: cyclesData } = useQuery({
    queryKey: ['joint-students', 'cycles'],
    queryFn: () => listCycles(),
  });
  const cycles = cyclesData?.data?.results || cyclesData?.data || [];

  // 默认选最近一个 collecting / closed 批次
  const activeCycleId = useMemo(() => {
    if (cycleId) return cycleId;
    const candidates = cycles.filter((c) => c.status === 'collecting' || c.status === 'closed');
    return candidates.length ? candidates[0].id : undefined;
  }, [cycleId, cycles]);

  const { data: reportsData, isLoading: reportsLoading } = useQuery({
    queryKey: ['joint-students', 'reports', 'approved', activeCycleId],
    queryFn: () => listReports({ status: 'approved' }),
  });
  const reports = reportsData?.data?.results || reportsData?.data || [];

  const { data: scoresData, isLoading: scoresLoading } = useQuery({
    queryKey: ['joint-students', 'scores', activeCycleId],
    queryFn: () => (activeCycleId ? listScores({ cycle: activeCycleId }) : Promise.resolve({ data: [] })),
    enabled: Boolean(activeCycleId),
  });
  const myScores = scoresData?.data?.results || scoresData?.data || [];

  const scoreMap = useMemo(() => {
    const map = new Map();
    myScores.forEach((s) => map.set(s.joint_student, s));
    return map;
  }, [myScores]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['joint-students', 'scores'] });
  };

  const submitMutation = useMutation({
    mutationFn: (values) =>
      createScore({
        cycle: activeCycleId,
        joint_student: scoreModal.record.joint_student,
        score: values.score,
        comment: values.comment,
      }),
    onSuccess: () => {
      message.success('已提交打分');
      invalidate();
      setScoreModal({ open: false, record: null });
      form.resetFields();
    },
    onError: () => message.error('提交失败'),
  });

  const columns = [
    { title: '联培生', dataIndex: 'student_name' },
    { title: '学号', dataIndex: 'student_id' },
    { title: '月份', key: 'month', render: (_, r) => `${r.year}-${String(r.month).padStart(2, '0')}` },
    {
      title: '出勤',
      key: 'attendance',
      render: (_, r) => `${r.attendance_days_actual} / ${r.attendance_days_expected}`,
    },
    {
      title: '我的分数',
      key: 'myScore',
      render: (_, r) => {
        const existing = scoreMap.get(r.joint_student);
        if (existing) return <Tag color="green">{existing.score}</Tag>;
        return <Tag>未打分</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, r) => {
        const existing = scoreMap.get(r.joint_student);
        if (existing) return <Tag color="default">已锁定</Tag>;
        return (
          <Button
            type="primary"
            size="small"
            onClick={() => setScoreModal({ open: true, record: r })}
          >
            打分
          </Button>
        );
      },
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>专家打分</h2>
      <Space style={{ marginBottom: 16 }} wrap>
        <span>批次：</span>
        {cycles.length === 0 ? (
          <Tag>暂无批次</Tag>
        ) : (
          cycles.map((c) => (
            <Button
              key={c.id}
              type={c.id === activeCycleId ? 'primary' : 'default'}
              size="small"
              onClick={() => setCycleId(c.id)}
            >
              {c.year}-{String(c.month).padStart(2, '0')}（{c.status}）
            </Button>
          ))
        )}
      </Space>
      <DataTable
        rowKey="id"
        loading={reportsLoading || scoresLoading}
        dataSource={reports}
        columns={columns}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }}
        showActions={false}
      />
      <Modal
        title="专家打分"
        open={scoreModal.open}
        onCancel={() => setScoreModal({ open: false, record: null })}
        onOk={() => form.submit()}
        confirmLoading={submitMutation.isPending}
        okText="提交"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={(v) => submitMutation.mutate(v)}>
          <Form.Item
            label="分数（0-100）"
            name="score"
            rules={[{ required: true, message: '请输入分数' }]}
          >
            <InputNumber min={0} max={100} step={0.5} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="评语" name="comment">
            <Input.TextArea rows={3} placeholder="可选评语" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
