import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Select, message } from 'antd';
import instance from '../api/axiosConfig';

const { Option } = Select;

const UserPersonnelManagementPage = () => {
    const [users, setUsers] = useState([]);
    const [personnelList, setPersonnelList] = useState([]);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [currentUser, setCurrentUser] = useState(null);
    const [selectedPersonnel, setSelectedPersonnel] = useState(null);

    useEffect(() => {
        fetchUsers();
        fetchPersonnel();
    }, []);

    const fetchUsers = async () => {
        try {
            const response = await instance.get('/api/users/personnel/');
            setUsers(response.data.results);
        } catch (error) {
            message.error('获取用户列表失败');
            console.error('Error fetching users:', error);
        }
    };

    const fetchPersonnel = async () => {
        try {
            const response = await instance.get('/api/users/personnel/');
            setPersonnelList(response.data.results);
        } catch (error) {
            message.error('获取人员列表失败');
            console.error('Error fetching personnel:', error);
        }
    };

    const handleAssociate = (user) => {
        setCurrentUser(user);
        setSelectedPersonnel(user.personnel ? user.personnel.id : null);
        setIsModalVisible(true);
    };

    const handleModalOk = async () => {
        if (!currentUser) return;

        try {
            await instance.patch(`/api/users/personnel/${currentUser.id}/`, {
                personnel_id: selectedPersonnel
            });
            message.success('关联成功');
            fetchUsers(); // 刷新用户列表
            setIsModalVisible(false);
        } catch (error) {
            message.error('关联失败');
            console.error('Error associating personnel:', error);
        }
    };

    const handleModalCancel = () => {
        setIsModalVisible(false);
        setCurrentUser(null);
        setSelectedPersonnel(null);
    };

    const columns = [
        {
            title: '用户名',
            dataIndex: 'username',
            key: 'username',
        },
        {
            title: '关联人员',
            dataIndex: 'personnel',
            key: 'personnel',
            render: (personnel) => personnel ? personnel.name : '未关联',
        },
        {
            title: '操作',
            key: 'action',
            render: (_, record) => (
                <Button type="primary" onClick={() => handleAssociate(record)}>
                    {record.personnel ? '修改关联' : '关联人员'}
                </Button>
            ),
        },
    ];

    return (
        <div style={{ padding: '20px' }}>
            <h1>用户人员关联管理</h1>
            <Table dataSource={users} columns={columns} rowKey="id" />

            <Modal
                title="关联人员"
                visible={isModalVisible}
                onOk={handleModalOk}
                onCancel={handleModalCancel}
            >
                <p>为用户 <strong>{currentUser?.username}</strong> 关联人员:</p>
                <Select
                    showSearch
                    placeholder="选择人员"
                    optionFilterProp="children"
                    onChange={(value) => setSelectedPersonnel(value)}
                    value={selectedPersonnel}
                    style={{ width: '100%' }}
                    filterOption={(input, option) =>
                        option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
                    }
                >
                    <Option value="">不关联任何人员</Option>
                    {personnelList.map(personnel => (
                        <Option key={personnel.id} value={personnel.id}>
                            {personnel.name}
                        </Option>
                    ))}
                </Select>
            </Modal>
        </div>
    );
};

export default UserPersonnelManagementPage;