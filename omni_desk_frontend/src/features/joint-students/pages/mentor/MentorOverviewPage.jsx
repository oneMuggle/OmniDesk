import { useMemo } from 'react';
import { Tag, Empty } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { listStudents } from '../../api/students';
import { listReports } from '../../api/reports';
import DataTable from '../../../../shared/components/DataTable';

const STATUS_LABEL = {
  draft: { label: '草稿', color: 'default' },
  submitted: { label: '待审核', color: 'gold' },
  approved: { label: '已通过', color: 'green' },
  rejected: { label: '已驳回', color: 'red' },
};

export default function MentorOverviewPage() {
  // 导师视图：仅展示名下联培生及本月报告状态
  const { data: studentsData, isLoading: studentsLoading } = useQuery({
    queryKey: ['joint-students', 'mentor-students'],
    queryFn: () => listStudents(),
  });
  const students = studentsData?.data?.results || studentsData?.data || [];

  const month = new Date();
  const y = month.getFullYear();
  const m = month.getMonth() + 1;

  const { data: reportsData } = useQuery({
    queryKey: ['joint-students', 'mentor-reports', y, m],
    queryFn: () => listReports({ year: y, month: m }),
  });
  const reports = reportsData?.data?.results || reportsData?.data || [];

  const reportMap = useMemo(() => {
    const map = new Map();
    reports.forEach((r) => map.set(r.joint_student, r));
    return map;
  }, [reports]);

  const columns = [
    { title: '学号', dataIndex: 'student_id' },
    { title: '姓名', dataIndex: 'personnel_name' },
    {
      title: '类型',
      dataIndex: 'student_type',
      render: (t) => (t === 'master' ? '硕士' : '博士'),
    },
    {
      title: `本月报告(${y}-${String(m).padStart(2, '0')})`,
      key: 'report',
      render: (_, r) => {
        const report = reportMap.get(r.id);
        if (!report) return <Tag>未提交</Tag>;
        const cfg = STATUS_LABEL[report.status] || { label: report.status, color: 'default' };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '出勤(实/应)',
      key: 'attendance',
      render: (_, r) => {
        const report = reportMap.get(r.id);
        if (!report) return '-';
        return `${report.attendance_days_actual} / ${report.attendance_days_expected}`;
      },
    },
  ];

  if (!studentsLoading && students.length === 0) {
    return (
      <div style={{ padding: 24 }}>
        <h2 style={{ marginBottom: 16 }}>我的联培生</h2>
        <Empty description="当前账号未关联导师身份或名下无联培生" />
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>我的联培生</h2>
      <DataTable
        rowKey="id"
        loading={studentsLoading}
        dataSource={students}
        columns={columns}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }}
        showActions={false}
      />
    </div>
  );
}
