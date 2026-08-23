import { useMemo } from 'react';
import { Card, Row, Col, Statistic } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { listStipends } from '../../api/stipends';
import GradeBadge from '../../components/GradeBadge';
import DataTable from '../../../../shared/components/DataTable';

export default function MyStipendsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['joint-students', 'my-stipends'],
    queryFn: () => listStipends({ status: 'locked' }),
  });
  const rows = data?.data?.results || data?.data || [];

  const totals = useMemo(() => {
    const total = rows.reduce((sum, r) => sum + parseFloat(r.final_amount || 0), 0);
    const year = new Date().getFullYear();
    const yearTotal = rows
      .filter((r) => r.cycle && r.cycle.year === year)
      .reduce((sum, r) => sum + parseFloat(r.final_amount || 0), 0);
    return { total, yearTotal };
  }, [rows]);

  const columns = [
    { title: '批次', key: 'cycle', render: (_, r) => `${r.cycle?.year}-${String(r.cycle?.month).padStart(2, '0')}` },
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
      title: '最终补助',
      dataIndex: 'final_amount',
      render: (v) => `${parseFloat(v).toFixed(2)} 元`,
    },
    { title: '锁定日期', dataIndex: 'locked_at' },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>我的补助</h2>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="本年累计" value={totals.yearTotal} precision={2} suffix="元" />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="累计发放" value={totals.total} precision={2} suffix="元" />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="记录数" value={rows.length} suffix="条" />
          </Card>
        </Col>
      </Row>
      <DataTable
        rowKey="id"
        loading={isLoading}
        dataSource={rows}
        columns={columns}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }}
        showActions={false}
      />
    </div>
  );
}
