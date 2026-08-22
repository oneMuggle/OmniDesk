import PropTypes from 'prop-types';
import { Select, Button, Space, Avatar } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import DataTable from '../../../../shared/components/DataTable';
import { logger } from '../../../../shared/utils/logger';

const { Option } = Select;

/**
 * 用户列表表格 — UserManagementPage 拆分出的展示子组件。
 * userColumns 定义逐字由原页面移入,关联人员/用户组 Select 依赖经 props 传入。
 */
const UserListTable = ({ users, personnel, groups, currentUserId, onGroupsChange, onAssociationChange }) => {
    const userColumns = [
        {
            title: '头像',
            dataIndex: 'avatar',
            key: 'avatar',
            render: (avatar) => <Avatar src={avatar} />,
        },
        { title: '用户名', dataIndex: 'username', key: 'username' },
        { title: '邮箱', dataIndex: 'email', key: 'email' },
        {
            title: '电话号码',
            dataIndex: 'phone_numbers',
            key: 'phone_numbers',
            render: phoneNumbers => (
                <span>
                    {phoneNumbers && phoneNumbers.map(pn => pn.number).join(', ')}
                </span>
            ),
        },
        {
            title: '关联人员',
            dataIndex: 'personnel',
            key: 'personnel',
            render: (personnelData, record) => (
                <Select
                    value={personnelData ? personnelData.id : null}
                    style={{ width: 200 }}
                    onChange={(value) => onAssociationChange(record.id, value)}
                    allowClear
                >
                    {personnel.map((p) => (
                        <Option key={p.id} value={p.id}>
                            {p.name}
                        </Option>
                    ))}
                </Select>
            ),
        },
        {
            title: '用户组',
            dataIndex: 'groups',
            key: 'groups',
            render: (groupIds, record) => (
                <Select
                    mode="multiple"
                    value={groupIds}
                    style={{ width: '100%' }}
                    placeholder="选择用户组"
                    onChange={values => onGroupsChange(record.id, values)}
                    disabled={currentUserId === record.id}
                >
                    {groups.map(group => (
                        <Option key={group.id} value={group.id}>{group.name}</Option>
                    ))}
                </Select>
            ),
        },
        {
            title: '加入日期',
            dataIndex: 'date_joined',
            key: 'date_joined',
            render: text => new Date(text).toLocaleDateString(),
        },
        {
            title: '操作',
            key: 'action',
            render: (text, record) => (
                <Space size="middle">
                    {record.permissions?.can_change && <Button data-testid="edit-user-button" type="primary" icon={<EditOutlined />} onClick={() => logger.warn('Edit user handler not implemented', record.id)}>编辑</Button>}
                    {record.permissions?.can_delete && <Button data-testid="delete-user-button" type="danger" icon={<DeleteOutlined />} onClick={() => logger.warn('Delete user handler not implemented', record.id)}>删除</Button>}
                </Space>
            ),
        },
    ];

    return (
        <DataTable
            columns={userColumns}
            dataSource={users}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            showActions={false}
        />
    );
};

UserListTable.propTypes = {
    users: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
        username: PropTypes.string,
        email: PropTypes.string,
    })),
    personnel: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
        name: PropTypes.string,
    })),
    groups: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
        name: PropTypes.string,
    })),
    currentUserId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    onGroupsChange: PropTypes.func.isRequired,
    onAssociationChange: PropTypes.func.isRequired,
};

export default UserListTable;
