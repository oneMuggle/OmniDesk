import React from 'react';
import { Table, Space, Button } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import SkeletonTable from '../SkeletonTable';

/**
 * DataTable — CRUD 列表页统一表格封装。
 *
 * 内建能力:loading + scroll(max-content)+ actions 操作列 + locale 空态模板;
 * R5-D4 扩展(全部向后兼容,缺省行为与旧版一致):
 * - actionAlign        操作列对齐('left' | 'center' | 'right'),透传给 antd column.align
 * - rowSelection       行选择配置,原样透传给 antd Table
 * - extraColumns       追加在操作列之后的尾部自定义列
 */
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
  actionAlign,
  rowSelection,
  extraColumns = [],
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

  // actionAlign 仅在显式传入时生效(缺省不注入 align 字段,保持旧行为)
  if (actionAlign) {
    actionColumn.align = actionAlign;
  }

  let finalColumns = columns;
  if (showActions) {
    finalColumns = [...columns, actionColumn];
  }
  if (extraColumns.length > 0) {
    finalColumns = [...finalColumns, ...extraColumns];
  }

  return (
    <Table
      columns={finalColumns}
      dataSource={dataSource}
      loading={loading}
      pagination={pagination}
      rowKey={rowKey}
      rowSelection={rowSelection}
      scroll={{ x: 'max-content' }}
      locale={{
        emptyText: loading ? '' : '暂无数据',
      }}
      {...props}
    />
  );
};

DataTable.propTypes = {
  columns: PropTypes.array,
  dataSource: PropTypes.array,
  loading: PropTypes.bool,
  pagination: PropTypes.oneOfType([PropTypes.object, PropTypes.bool]),
  rowKey: PropTypes.string,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
  editText: PropTypes.string,
  deleteText: PropTypes.string,
  showActions: PropTypes.bool,
  /** R5-D4:操作列对齐('left' | 'center' | 'right') */
  actionAlign: PropTypes.oneOf(['left', 'center', 'right']),
  /** R5-D4:行选择配置,原样透传 antd Table.rowSelection */
  rowSelection: PropTypes.object,
  /** R5-D4:追加在操作列之后的尾部自定义列 */
  extraColumns: PropTypes.array,
};

export default DataTable;
