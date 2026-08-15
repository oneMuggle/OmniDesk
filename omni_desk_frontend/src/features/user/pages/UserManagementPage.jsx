import { Spin, Card, Tabs } from 'antd';
import useUserManagementPage from '../hooks/useUserManagementPage';
import UserListTable from '../components/userManagement/UserListTable';
import GroupPermissionManager from '../components/userManagement/GroupPermissionManager';

/**
 * 用户管理页面 — 薄壳。
 * 业务逻辑迁入 useUserManagementPage hook,用户列表拆为 UserListTable,
 * 用户组权限拆为 GroupPermissionManager 组合组件。
 */
const UserManagementPage = () => {
    const {
        users, groups, personnel, loading, currentUserId,
        fetchGroups,
        handleGroupsChange, handleAssociationChange,
    } = useUserManagementPage();

    const tabItems = [
        {
            key: '1',
            label: '用户列表',
            children: (
                <UserListTable
                    users={users}
                    personnel={personnel}
                    groups={groups}
                    currentUserId={currentUserId}
                    onGroupsChange={handleGroupsChange}
                    onAssociationChange={handleAssociationChange}
                />
            ),
        },
        {
            key: '2',
            label: '用户组与权限',
            children: <GroupPermissionManager groups={groups} fetchGroups={fetchGroups} />,
        },
    ];

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <Spin size="large" />
            </div>
        );
    }

    return (
        <div style={{ padding: '24px' }}>
            <h1>管理员面板</h1>
            <Card>
                <Tabs defaultActiveKey="1" items={tabItems} />
            </Card>
        </div>
    );
};

export default UserManagementPage;
