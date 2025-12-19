import React, { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { Table, Select, Button, message, Spin, Card, Tabs, Modal, Form, Input, Space, Tree, Row, Col, Avatar } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import userManagementApi from '../features/authentication/api/userManagementApi';
import { getAllPersonnel } from '../features/personnel/api/personnelApi';
import { permissionsApi } from '../features/authentication/api/permissionsApi';
import { useAuth } from '../context/AuthContext';

const { Option } = Select;
const { TabPane } = Tabs;
const { Search } = Input;

// Helper function to get all keys from the tree data
const getAllKeys = (tree) => {
    let keys = [];
    for (const node of tree) {
        keys.push(node.key);
        if (node.children) {
            keys = keys.concat(getAllKeys(node.children));
        }
    }
    return keys;
};

const GroupPermissionManager = ({ groups, fetchGroups }) => {
    const [selectedGroupId, setSelectedGroupId] = useState(null);
    const [permissions, setPermissions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [checkedKeys, setCheckedKeys] = useState([]);
    const [expandedKeys, setExpandedKeys] = useState([]);
    const [searchValue, setSearchValue] = useState('');
    const [autoExpandParent, setAutoExpandParent] = useState(true);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [editingGroup, setEditingGroup] = useState(null);
    const [form] = Form.useForm();

    useEffect(() => {
        fetchPermissions();
    }, []);

    useEffect(() => {
        if (selectedGroupId) {
            fetchGroupPermissions(selectedGroupId);
        } else {
            setCheckedKeys([]);
        }
    }, [selectedGroupId]);

    const fetchPermissions = async () => {
        try {
            const res = await userManagementApi.getGroupedPermissions();
            const data = res.data;
            const formattedTreeData = Object.keys(data).map(groupName => ({
                title: groupName,
                key: groupName,
                children: (data[groupName] || []).map(perm => ({
                    title: perm.name,
                    key: perm.id,
                })),
            }));
            setPermissions(formattedTreeData);
        } catch (error) {
            message.error('获取权限列表失败');
        }
    };

    const fetchGroupPermissions = async (groupId) => {
        setLoading(true);
        try {
            const res = await userManagementApi.getGroupPermissions(groupId);
            setCheckedKeys(res.data);
        } catch (error) {
            message.error('获取用户组权限失败');
        } finally {
            setLoading(false);
        }
    };

    const handleGroupChange = (groupId) => {
        setSelectedGroupId(groupId);
    };

    const handleSavePermissions = async () => {
        if (!selectedGroupId) {
            message.warn('请先选择一个用户组');
            return;
        }
        setLoading(true);
        try {
            await userManagementApi.updateGroupPermissions(selectedGroupId, checkedKeys);
            message.success('权限更新成功');
        } catch (error) {
            message.error('权限更新失败');
        } finally {
            setLoading(false);
        }
    };

    const onExpand = (newExpandedKeys) => {
        setExpandedKeys(newExpandedKeys);
        setAutoExpandParent(false);
    };

    const onCheck = (checked) => {
        setCheckedKeys(checked);
    };

    const onSearch = (e) => {
        const { value } = e.target;
        const newExpandedKeys = permissions
            .map((item) => {
                if (item.children.some(child => child.title.toLowerCase().includes(value.toLowerCase()))) {
                    return item.key;
                }
                return null;
            })
            .filter((item, i, self) => item && self.indexOf(item) === i);
        
        setExpandedKeys(newExpandedKeys);
        setSearchValue(value);
        setAutoExpandParent(true);
    };

    const generatedTreeData = useMemo(() => {
        const loop = (data) =>
            data.map((item) => {
                const strTitle = item.title;
                const index = strTitle.toLowerCase().indexOf(searchValue.toLowerCase());
                const beforeStr = strTitle.substring(0, index);
                const afterStr = strTitle.slice(index + searchValue.length);
                const title =
                    index > -1 ? (
                        <span>
                            {beforeStr}
                            <span style={{ color: '#f50' }}>{strTitle.substring(index, index + searchValue.length)}</span>
                            {afterStr}
                        </span>
                    ) : (
                        <span>{strTitle}</span>
                    );
                if (item.children) {
                    return { title: item.title, key: item.key, children: loop(item.children) };
                }
                return {
                    title,
                    key: item.key,
                };
            });

        if (!searchValue) {
            return permissions;
        }
        const filteredData = permissions.map(group => {
            const filteredChildren = group.children.filter(perm => perm.title.toLowerCase().includes(searchValue.toLowerCase()));
            if (filteredChildren.length > 0) {
                return { ...group, children: loop(filteredChildren) };
            }
            return null;
        }).filter(Boolean);

        return loop(filteredData);
    }, [searchValue, permissions]);

    const allKeys = useMemo(() => getAllKeys(permissions), [permissions]);

    const showModal = (group = null) => {
        setEditingGroup(group);
        form.setFieldsValue({ name: group ? group.name : '' });
        setIsModalVisible(true);
    };

    const handleCancel = () => {
        setIsModalVisible(false);
        setEditingGroup(null);
        form.resetFields();
    };

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            if (editingGroup) {
                await permissionsApi.updateGroup(editingGroup.id, values);
                message.success('用户组更新成功');
            } else {
                await permissionsApi.createGroup(values);
                message.success('用户组创建成功');
            }
            fetchGroups();
            handleCancel();
        } catch (error) {
            message.error('操作失败');
        }
    };

    const handleDelete = (groupId) => {
        Modal.confirm({
            title: '确定要删除这个用户组吗？',
            content: '删除后，该用户组的权限配置将一并被移除。',
            okText: '确定',
            okType: 'danger',
            cancelText: '取消',
            onOk: async () => {
                try {
                    await permissionsApi.deleteGroup(groupId);
                    message.success('用户组删除成功');
                    if (selectedGroupId === groupId) {
                        setSelectedGroupId(null);
                    }
                    fetchGroups();
                } catch (error) {
                    message.error('删除失败');
                }
            },
        });
    };

    return (
        <Card title="用户组权限管理">
            <Row gutter={[16, 16]}>
                <Col span={24}>
                    <Space>
                        <Select
                            style={{ width: 250 }}
                            placeholder="请选择一个用户组"
                            onChange={handleGroupChange}
                            value={selectedGroupId}
                        >
                            {groups.map(group => (
                                <Option key={group.id} value={group.id}>{group.name}</Option>
                            ))}
                        </Select>
                        <Button type="primary" onClick={() => showModal()}>创建用户组</Button>
                        <Button onClick={() => showModal(groups.find(g => g.id === selectedGroupId))} disabled={!selectedGroupId} icon={<EditOutlined />}>编辑用户组</Button>
                        <Button danger onClick={() => handleDelete(selectedGroupId)} disabled={!selectedGroupId} icon={<DeleteOutlined />}>删除用户组</Button>
                        <Button type="primary" onClick={handleSavePermissions} disabled={!selectedGroupId}>
                            保存权限
                        </Button>
                    </Space>
                </Col>
                <Col span={24}>
                    <Spin spinning={loading}>
                        <Card>
                            <Space style={{ marginBottom: 16 }}>
                                <Button onClick={() => setExpandedKeys(allKeys)}>全部展开</Button>
                                <Button onClick={() => setExpandedKeys([])}>全部折叠</Button>
                                <Search placeholder="搜索权限" onChange={onSearch} style={{ width: 300 }} />
                            </Space>
                            {selectedGroupId ? (
                                <Tree
                                    checkable
                                    onExpand={onExpand}
                                    expandedKeys={expandedKeys}
                                    autoExpandParent={autoExpandParent}
                                    onCheck={onCheck}
                                    checkedKeys={checkedKeys}
                                    treeData={generatedTreeData}
                                />
                            ) : (
                                <p>请先选择一个用户组以配置权限。</p>
                            )}
                        </Card>
                    </Spin>
                </Col>
            </Row>
            <Modal
                title={editingGroup ? '编辑用户组' : '新增用户组'}
                open={isModalVisible}
                onOk={handleOk}
                onCancel={handleCancel}
                okText="确定"
                cancelText="取消"
            >
                <Form form={form} layout="vertical" name="group_form">
                    <Form.Item
                        name="name"
                        label="用户组名称"
                        rules={[{ required: true, message: '请输入用户组名称' }]}
                    >
                        <Input />
                    </Form.Item>
                </Form>
            </Modal>
        </Card>
    );
};

GroupPermissionManager.propTypes = {
  groups: PropTypes.array.isRequired,
  fetchGroups: PropTypes.func.isRequired,
};


const UserManagementPage = () => {
    const { user: currentUser } = useAuth();
    const [users, setUsers] = useState([]);
    const [groups, setGroups] = useState([]);
    const [personnel, setPersonnel] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchUsers = async () => {
        try {
            const res = await userManagementApi.getAllUsers();
            setUsers(res.data.results || []);
        } catch (error) {
            message.error('获取用户列表失败');
        }
    };

    const fetchGroups = async () => {
        try {
            const res = await permissionsApi.getGroups();
            setGroups(res.results || []);
        } catch (error) {
            message.error('获取用户组列表失败');
        }
    };

    const fetchPersonnel = async () => {
        try {
            const response = await getAllPersonnel();
            setPersonnel(response || []);
        } catch (error) {
            message.error('获取人员数据失败');
        }
    };
 
    const fetchData = React.useCallback(async () => {
        setLoading(true);
        try {
            await Promise.all([fetchUsers(), fetchGroups(), fetchPersonnel()]);
        } catch (error) {
            // Errors are handled in individual fetch functions, but you could add a general one here if needed.
            console.error("An error occurred during initial data fetch:", error);
        } finally {
            setLoading(false);
        }
    }, []); // Dependencies are implicitly handled by useCallback if they are not changing.

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleGroupsChange = async (userId, groupIds) => {
        try {
            await userManagementApi.updateUserGroups(userId, groupIds);
            message.success('用户组更新成功');
            fetchUsers();
        } catch (error) {
            message.error('更新用户组失败');
        }
    };

    const handleAssociationChange = async (userId, personnelId) => {
        try {
          await userManagementApi.associateUserWithPersonnel(userId, personnelId);
          message.success('关联成功');
          fetchUsers(); // Refresh users to show updated data
        } catch (error) {
          message.error('关联失败');
        }
    };
 
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
                    onChange={(value) => handleAssociationChange(record.id, value)}
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
        {
            title: '操作',
            key: 'action',
            render: (text, record) => (
                <Space size="middle">
                    {record.permissions?.can_change && <Button type="primary" icon={<EditOutlined />} onClick={() => console.log('Edit user', record.id)}>编辑</Button>}
                    {record.permissions?.can_delete && <Button type="danger" icon={<DeleteOutlined />} onClick={() => console.log('Delete user', record.id)}>删除</Button>}
                </Space>
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
                        <GroupPermissionManager groups={groups} fetchGroups={fetchGroups} />
                    </TabPane>
                </Tabs>
            </Card>
        </div>
    );
};

export default UserManagementPage;