import React, { useState, useEffect } from 'react';
import { Table, Button, message, Spin, Modal, Form, Input, Select, Space } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import userManagementApi from '../api/userManagementApi';

const { Option } = Select;

const AdminUserManagementPage = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [editingUser, setEditingUser] = useState(null);
    const [form] = Form.useForm();

    useEffect(() => {
        fetchUsers();
    }, []);

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const res = await userManagementApi.getAllUsers();
            setUsers(res.data.results || []);
        } catch (error) {
            message.error('获取用户列表失败');
        } finally {
            setLoading(false);
        }
    };

    const handleAddUser = () => {
        setEditingUser(null);
        form.resetFields();
        setIsModalVisible(true);
    };

    const handleEditUser = (user) => {
        setEditingUser(user);
        form.setFieldsValue({
            ...user,
            phone_numbers: user.phone_numbers.map(pn => ({ number: pn.number })),
        });
        setIsModalVisible(true);
    };

    const handleCancel = () => {
        setIsModalVisible(false);
        setEditingUser(null);
    };

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            const phoneNumbers = values.phone_numbers ? values.phone_numbers.map(pn => pn.number) : [];
            
            const userData = {
                ...values,
                phone_numbers: phoneNumbers.map(number => ({ number })),
            };

            if (editingUser) {
                await userManagementApi.updateUser(editingUser.id, userData);
                message.success('用户更新成功');
            } else {
                await userManagementApi.createUser(userData);
                message.success('用户创建成功');
            }
            setIsModalVisible(false);
            fetchUsers();
        } catch (error) {
            message.error('操作失败');
        }
    };

    const columns = [
        { title: 'ID', dataIndex: 'id', key: 'id' },
        { title: '用户名', dataIndex: 'username', key: 'username' },
        { title: '邮箱', dataIndex: 'email', key: 'email' },
        { title: '真实姓名', dataIndex: 'real_name', key: 'real_name' },
        { title: '角色', dataIndex: 'role', key: 'role' },
        {
            title: '电话号码',
            dataIndex: 'phone_numbers',
            key: 'phone_numbers',
            render: phoneNumbers => (
                <ul>
                    {phoneNumbers.map(pn => (
                        <li key={pn.id}>{pn.number}</li>
                    ))}
                </ul>
            ),
        },
        {
            title: '操作',
            key: 'action',
            render: (_, record) => (
                <Button type="link" onClick={() => handleEditUser(record)}>
                    编辑
                </Button>
            ),
        },
    ];

    return (
        <div style={{ padding: '24px' }}>
            <h1>用户管理</h1>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleAddUser} style={{ marginBottom: 16 }}>
                添加用户
            </Button>
            <Spin spinning={loading}>
                <Table columns={columns} dataSource={users} rowKey="id" />
            </Spin>
            <Modal
                title={editingUser ? '编辑用户' : '添加用户'}
                visible={isModalVisible}
                onOk={handleOk}
                onCancel={handleCancel}
                destroyOnClose
            >
                <Form form={form} layout="vertical" name="userForm">
                    <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
                        <Input />
                    </Form.Item>
                    {!editingUser && (
                        <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
                            <Input.Password />
                        </Form.Item>
                    )}
                    <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '请输入有效的邮箱地址' }]}>
                        <Input />
                    </Form.Item>
                    <Form.Item name="real_name" label="真实姓名">
                        <Input />
                    </Form.Item>
                    <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
                        <Select>
                            <Option value="admin">管理员</Option>
                            <Option value="manager">经理</Option>
                            <Option value="user">普通用户</Option>
                        </Select>
                    </Form.Item>
                    <Form.List name="phone_numbers">
                        {(fields, { add, remove }) => (
                            <>
                                {fields.map(({ key, name, fieldKey, ...restField }) => (
                                    <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                                        <Form.Item
                                            {...restField}
                                            name={[name, 'number']}
                                            fieldKey={[fieldKey, 'number']}
                                            rules={[{ required: true, message: '请输入电话号码' }]}
                                        >
                                            <Input placeholder="电话号码" />
                                        </Form.Item>
                                        <MinusCircleOutlined onClick={() => remove(name)} />
                                    </Space>
                                ))}
                                <Form.Item>
                                    <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                                        添加电话号码
                                    </Button>
                                </Form.Item>
                            </>
                        )}
                    </Form.List>
                </Form>
            </Modal>
        </div>
    );
};

export default AdminUserManagementPage;