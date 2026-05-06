import React from 'react';
import { Table, Space, Button } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import SkeletonTable from '../SkeletonTable';

const DataTable = ({
  columns = [],
  dataSource = [],
  loading = false,
  pagination = false,
  rowKey = 'id',
  onEdit,
  onDelete,
  editText = '编辑',
  deleteText = '删除',
  showActions = true,
  ...props
}) => {
  const actionColumn = {
    title: '操作',
    key: 'actions',
    width: 150,
    render: (_, record) => (
      <Space size="middle">
        {onEdit && (
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => onEdit(record)}
          >
            {editText}
          </Button>
        )}
        {onDelete && (
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onDelete(record)}
          >
            {deleteText}
          </Button>
        )}
      </Space>
    ),
  };

  const finalColumns = showActions
    ? [...columns, actionColumn]
    : columns;

  return (
    <Table
      columns={finalColumns}
      dataSource={dataSource}
      loading={loading}
      pagination={pagination}
      rowKey={rowKey}
      scroll={{ x: 'max-content' }}
      locale={{
        emptyText: loading ? '' : '暂无数据',
      }}
      {...props}
    />
  );
};

export default DataTable;