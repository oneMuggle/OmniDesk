import { Button, Popconfirm, Space } from 'antd';
import dayjs from 'dayjs';

/**
 * 排班列表 Table columns 定义。
 * R4-B4: 从 ScheduleManagementPage.jsx 组件体内联提升为纯函数,
 * 行为/排序器/testid 与原内联完全一致。
 *
 * @param {(record: object) => void} onEdit 编辑回调(handleEdit)
 * @param {(id: number|string) => void} onDelete 删除回调(handleDelete)
 * @returns {Array<object>} Ant Design Table columns
 */
export const createScheduleColumns = (onEdit, onDelete) => [
  {
    title: '值班日期',
    dataIndex: 'duty_date',
    key: 'duty_date',
    sorter: (a, b) => dayjs(a.duty_date).unix() - dayjs(b.duty_date).unix(),
    sortOrder: 'ascend',
  },
  {
    title: '值班人员',
    dataIndex: ['duty_person', 'name'],
    key: 'duty_person',
  },
  {
    title: '值班人员电话',
    dataIndex: ['duty_person', 'phone_number'],
    key: 'duty_person_phone',
    render: (phone_number) => phone_number || 'N/A',
  },
  {
    title: '值班领导',
    dataIndex: ['duty_leader', 'name'],
    key: 'duty_leader',
  },
  {
    title: '值班领导电话',
    dataIndex: ['duty_leader', 'phone_number'],
    key: 'duty_leader_phone',
    render: (phone_number) => phone_number || 'N/A',
  },
  {
    title: '操作',
    key: 'action',
    render: (_, record) => (
      <Space size="middle">
        <Button type="primary" onClick={() => onEdit(record)} data-testid={`edit-schedule-button-${record.id}`}>编辑</Button>
        <Popconfirm title="确定删除吗?" onConfirm={() => onDelete(record.id)}>
          <Button danger data-testid={`delete-schedule-button-${record.id}`}>删除</Button>
        </Popconfirm>
      </Space>
    ),
  },
];
