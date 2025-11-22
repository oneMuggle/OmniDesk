import React, { useState, useEffect, useCallback } from 'react';
import { Table, Button, Select, message, Avatar } from 'antd';
import userManagementApi from '../api/userManagementApi';
import { getAllPersonnel } from '../api/personnelApi';

const { Option } = Select;

const UserPersonnelAssociation = () => {
  const [users, setUsers] = useState([]);
  const [personnel, setPersonnel] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const response = await userManagementApi.getAllUsers();
      setUsers(response.data.results);
    } catch (error) {
      message.error('获取用户数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPersonnel = useCallback(async () => {
    try {
      const response = await getAllPersonnel();
      setPersonnel(response);
    } catch (error) {
      message.error('获取人员数据失败');
    }
  }, []);

  useEffect(() => {
    fetchUsers();
    fetchPersonnel();
  }, [fetchUsers, fetchPersonnel]);

  const handleAssociationChange = async (userId, personnelId) => {
    try {
      await userManagementApi.associateUserWithPersonnel(userId, personnelId);
      message.success('关联成功');
      fetchUsers(); // Refresh users to show updated data
    } catch (error) {
      message.error('关联失败');
    }
  };

  const columns = [
    {
      title: '头像',
      dataIndex: 'avatar',
      key: 'avatar',
      render: (avatar) => <Avatar src={avatar} />,
    },
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '关联人员',
      dataIndex: 'personnel',
      key: 'personnel',
      render: (personnelId, record) => (
        <Select
          value={personnelId}
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
        title: '真实姓名',
        dataIndex: 'real_name',
        key: 'real_name',
    },
    {
        title: '联系电话',
        dataIndex: 'phone',
        key: 'phone',
    }
  ];

  return (
    <div>
      <Table
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        bordered
      />
    </div>
  );
};

export default UserPersonnelAssociation;