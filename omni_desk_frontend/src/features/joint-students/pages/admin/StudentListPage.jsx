import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Tag, Button, Space, Input, Select } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { listStudents } from '../../api/students';
import DataTable from '../../../../shared/components/DataTable';

const { Search } = Input;

const STATUS_FILTER = [
  { value: 'true', label: '在读' },
  { value: 'false', label: '已毕业' },
];

const TYPE_FILTER = [
  { value: 'master', label: '硕士' },
  { value: 'phd', label: '博士' },
];

export default function StudentListPage() {
  const navigate = useNavigate();
  const [studentId, setStudentId] = useState('');
  const [studentType, setStudentType] = useState();
  const [isActive, setIsActive] = useState();

  const { data, isLoading } = useQuery({
    queryKey: ['joint-students', 'list', { studentId, studentType, isActive }],
    queryFn: () => {
      const params = {};
      if (studentId) params.student_id = studentId;
      if (studentType) params.student_type = studentType;
      if (isActive) params.is_active = isActive;
      return listStudents(params);
    },
  });

  const rows = data?.data?.results || data?.data || [];

  const columns = [
    { title: '学号', dataIndex: 'student_id' },
    { title: '姓名', dataIndex: 'personnel_name' },
    {
      title: '类型',
      dataIndex: 'student_type',
      render: (t) => (t === 'master' ? <Tag color="blue">硕士</Tag> : <Tag color="purple">博士</Tag>),
    },
    { title: '入学日期', dataIndex: 'enrollment_date' },
    { title: '导师', dataIndex: 'mentor_name' },
    {
      title: '状态',
      dataIndex: 'is_active',
      render: (active) => (active ? <Tag color="green">在读</Tag> : <Tag>已毕业</Tag>),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Link to={`/joint-students/admin/students/${record.id}`}>详情</Link>
          <Link to={`/joint-students/admin/students/${record.id}/edit`}>编辑</Link>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>联培生列表</h2>
      <Space style={{ marginBottom: 16 }} wrap>
        <Search
          placeholder="按学号搜索"
          allowClear
          onSearch={setStudentId}
          style={{ width: 200 }}
        />
        <Select
          placeholder="联培生类型"
          allowClear
          options={TYPE_FILTER}
          onChange={setStudentType}
          style={{ width: 140 }}
        />
        <Select
          placeholder="状态"
          allowClear
          options={STATUS_FILTER}
          onChange={setIsActive}
          style={{ width: 120 }}
        />
        <Button
          type="primary"
          onClick={() => navigate('/joint-students/admin/students/new')}
        >
          新增联培生
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
    </div>
  );
}
