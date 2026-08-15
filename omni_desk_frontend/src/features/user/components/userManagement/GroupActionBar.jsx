import PropTypes from 'prop-types';
import { Button, Select, Space } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';

const { Option } = Select;

/**
 * 组操作栏 — 用户组权限矩阵顶部的组选择 + 创建/编辑/删除/保存按钮组。
 * 由 GroupPermissionManager 拆出,原 JSX 逐字搬入。
 */
const GroupActionBar = ({ groups, selectedGroupId, onGroupChange, onCreate, onClickEdit, onClickDelete, onSavePermissions }) => (
    <Space>
        <Select
            style={{ width: 250 }}
            placeholder="请选择一个用户组"
            onChange={onGroupChange}
            value={selectedGroupId}
        >
            {groups.map(group => (
                <Option key={group.id} value={group.id}>{group.name}</Option>
            ))}
        </Select>
        <Button type="primary" onClick={() => onCreate()}>创建用户组</Button>
        <Button onClick={() => onClickEdit()} disabled={!selectedGroupId} icon={<EditOutlined />}>编辑用户组</Button>
        <Button danger onClick={() => onClickDelete()} disabled={!selectedGroupId} icon={<DeleteOutlined />}>删除用户组</Button>
        <Button type="primary" onClick={onSavePermissions} disabled={!selectedGroupId}>
            保存权限
        </Button>
    </Space>
);

GroupActionBar.propTypes = {
    groups: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
        name: PropTypes.string,
    })),
    selectedGroupId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    onGroupChange: PropTypes.func.isRequired,
    onCreate: PropTypes.func.isRequired,
    onClickEdit: PropTypes.func.isRequired,
    onClickDelete: PropTypes.func.isRequired,
    onSavePermissions: PropTypes.func.isRequired,
};

export default GroupActionBar;
