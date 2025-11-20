import React from 'react';
import { Table, Button, Space } from 'antd';

const BookList = ({ books, onEdit, onExport, loading }) => {
  const columns = [
    {
      title: '书名',
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: '作者',
      dataIndex: 'author',
      key: 'author',
    },
    {
      title: '创建日期',
      dataIndex: 'createdAt',
      key: 'createdAt',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button type="primary" onClick={() => onEdit(record)}>
            编辑
          </Button>
          <Button onClick={() => onExport(record)}>
            导出
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={books}
      rowKey="id"
      loading={loading}
      pagination={{ pageSize: 10 }}
    />
  );
};

export default BookList;