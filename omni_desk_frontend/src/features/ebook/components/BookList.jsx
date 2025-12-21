import PropTypes from 'prop-types';
import { Table, Button, Space, Popconfirm } from 'antd';

const BookList = ({ books, onEdit, onDelete, onExport, loading }) => {
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
          <Button type="primary" onClick={() => onEdit(record)} data-testid={`edit-book-${record.id}`}>
            编辑
          </Button>
          <Popconfirm
            title="您确定要删除这本电子书吗？"
            onConfirm={() => onDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button danger data-testid={`delete-book-${record.id}`}>
              删除
            </Button>
          </Popconfirm>
          <Button onClick={() => onExport(record)} data-testid={`export-book-${record.id}`}>
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

BookList.propTypes = {
  books: PropTypes.array.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onExport: PropTypes.func.isRequired,
  loading: PropTypes.bool.isRequired,
};

export default BookList;