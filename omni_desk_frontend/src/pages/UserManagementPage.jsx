import React, { useState, useEffect } from 'react';
import { Table, Select, Button, message, Spin, Card, Switch } from 'antd';
import userManagementApi from '../api/userManagementApi';
import pageConfigApi from '../api/pageConfigApi';
import { useAuth } from '../context/AuthContext';

const { Option } = Select;

const UserManagementPage = () => {
    const { user: currentUser } = useAuth();
    const [users, setUsers] = useState([]);
    const [pageConfigs, setPageConfigs] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [usersRes, pageConfigsRes] = await Promise.all([
                userManagementApi.getAllUsers(),
                pageConfigApi.getAllPageConfigs(),
            ]);
            setUsers(usersRes.data.results || []);
            setPageConfigs(pageConfigsRes.data.results || []);
        } catch (error) {
            message.error('获取数据失败');
            console.error('Failed to fetch data:', error);
        } finally {
            setLoading(false);
        }
    };

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

    const handlePageVisibilityChange = async (pagePath, isHidden) => {
        try {
            await pageConfigApi.updatePageConfig(pagePath, { is_hidden_for_non_admin: isHidden });
            message.success('页面可见性更新成功');
            setPageConfigs(prevConfigs =>
                prevConfigs.map(config =>
                    config.page_path === pagePath ? { ...config, is_hidden_for_non_admin: isHidden } : config
                )
            );
        } catch (error) {
            message.error('更新页面可见性失败');
            console.error('Failed to update page visibility:', error);
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
            title: '加入日期',
            dataIndex: 'date_joined',
            key: 'date_joined',
            render: text => new Date(text).toLocaleDateString(),
        },
    ];

    const pageConfigColumns = [
        {
            title: '页面名称',
            dataIndex: 'page_name',
            key: 'page_name',
        },
        {
            title: '页面路径',
            dataIndex: 'page_path',
            key: 'page_path',
        },
        {
            title: '对非管理员隐藏',
            dataIndex: 'is_hidden_for_non_admin',
            key: 'is_hidden_for_non_admin',
            render: (text, record) => (
                <Switch
                    checked={text}
                    onChange={checked => handlePageVisibilityChange(record.page_path, checked)}
                />
            ),
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

            <Card title="用户管理" style={{ marginBottom: '24px' }}>
                <Table
                    columns={userColumns}
                    dataSource={users}
                    rowKey="id"
                    pagination={{ pageSize: 10 }}
                />
            </Card>

            <Card title="页面可见性管理">
                <Table
                    columns={pageConfigColumns}
                    dataSource={pageConfigs}
                    rowKey="page_path"
                    pagination={{ pageSize: 10 }}
                />
            </Card>
        </div>
    );
};

export default UserManagementPage;