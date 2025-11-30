import React, { useState, useEffect } from 'react';
import { Table, Select, Button, message, Spin, Card, Tabs } from 'antd';
import userManagementApi from '../api/userManagementApi';
import { permissionsApi } from '../api/permissionsApi';
import { useAuth } from '../context/AuthContext';
import GroupPermissionManager from '../components/Admin/GroupPermissionManager';

const { Option } = Select;
const { TabPane } = Tabs;

const UserManagementPage = () => {
    const { user: currentUser } = useAuth();
    const [users, setUsers] = useState([]);
    const [groups, setGroups] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [usersRes, groupsRes] = await Promise.all([
                userManagementApi.getAllUsers(),
                permissionsApi.getGroups(),
            ]);
            setUsers(usersRes.data.results || []);
            setGroups(groupsRes.results || []);
        } catch (error) {
            message.error('获取数据失败');
            console.error('Failed to fetch data:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleRoleChange = async (userId, newRole) => {
        try {
            await userManagementApi.updateUserRole(userId, newRole);
            message.success('用户角色更新成功');
            setUsers(prevUsers =>
                prevUsers.map(user => (user.id === userId ? { ...user, role: newRole } : user))
            );
        } catch (error) {
            message.error('更新用户角色失败');
            console.error('Failed to update user role:', error);
        }
    };

    const handleGroupsChange = async (userId, groupIds) => {
        try {
            await userManagementApi.updateUserGroups(userId, groupIds);
            message.success('用户组更新成功');
            setUsers(prevUsers =>
                prevUsers.map(user => (user.id === userId ? { ...user, groups: groupIds } : user))
            );
        } catch (error) {
            message.error('更新用户组失败');
            console.error('Failed to update user groups:', error);
        }
    };

    const userColumns = [
        {
            title: 'ID',
            dataIndex: 'id',
            key: 'id',
        },
        {
            title: '用户名',
            dataIndex: 'username',
            key: 'username',
        },
        {
            title: '邮箱',
            dataIndex: 'email',
            key: 'email',
        },
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
            title: '角色',
            dataIndex: 'role',
            key: 'role',
            render: (text, record) => (
                <Select
                    value={text}
                    style={{ width: 120 }}
                    onChange={value => handleRoleChange(record.id, value)}
                    disabled={currentUser.id === record.id} // 不允许修改自己的角色
                >
                    <Option value="admin">管理员</Option>
                    <Option value="manager">经理</Option>
                    <Option value="user">普通用户</Option>
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
                    onChange={values => handleGroupsChange(record.id, values)}
                    disabled={currentUser.id === record.id}
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
                <Tabs defaultActiveKey="1">
                    <TabPane tab="用户列表" key="1">
                        <Table
                            columns={userColumns}
                            dataSource={users}
                            rowKey="id"
                            pagination={{ pageSize: 10 }}
                        />
                    </TabPane>
                    <TabPane tab="用户组与权限" key="2">
                        <GroupPermissionManager />
                    </TabPane>
                </Tabs>
            </Card>
        </div>
    );
};

export default UserManagementPage;