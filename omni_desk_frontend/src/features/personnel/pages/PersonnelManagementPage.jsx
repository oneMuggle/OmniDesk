import React, { useState, useEffect, useCallback } from 'react';
import { Table, Button, Form, Input, Modal, message, Select, Tabs, Space } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { Link, useParams } from 'react-router-dom';
import {
  getPersonnel,
  createPersonnel,
  updatePersonnel,
  deletePersonnel,
  getPositions,
} from '../api/personnelApi';
import PositionManagementTab from '../components/PositionManagementTab';

const { Option } = Select;

const PersonnelManagementPage = () => {
  const { id } = useParams();
  const [form] = Form.useForm();
  const [data, setData] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [positions, setPositions] = useState([]);
  const [positionsLoaded, setPositionsLoaded] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [positionFilter, setPositionFilter] = useState(null);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });
  const [activeTab, setActiveTab] = useState('personnel');

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name' },
    {
      title: '职位',
      dataIndex: 'position',
      key: 'position',
      render: (positionId) => {
        const position = positions.find(p => p.id === positionId);
        return position ? position.name : '未分配';
      },
    },
    { title: '联系电话', dataIndex: 'phone_number', key: 'phone_number' },
    { title: '部门', dataIndex: 'department', key: 'department' },
    { title: '员工状态', dataIndex: 'status', key: 'status' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Link to={`/control-panel/personnel/${record.id}`}>
            <Button>详情</Button>
          </Link>
          <Button type="primary" icon={<EditOutlined />} onClick={() => showEditModal(record)} data-testid={`edit-personnel-${record.id}`} />
          <Button danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)} data-testid={`delete-personnel-${record.id}`} />
        </Space>
      ),
    },
  ];

  const fetchData = useCallback(async (page, pageSize, search, position) => {
    try {
      if (id) {
        const response = await getPersonnel(id);
        const data = response && response.id ? [response] : [];
        setData(data);
        setPagination(prev => ({ ...prev, total: data.length, current: 1, pageSize: 10 }));
      } else {
        const response = await getPersonnel({ page, page_size: pageSize, search, position });
        if (response && response.results) {
          setData(response.results);
          setPagination(prev => ({ ...prev, total: response.count, current: page, pageSize }));
        } else {
          setData([]);
          setPagination(prev => ({ ...prev, total: 0, current: page, pageSize }));
        }
      }
    } catch (error) {
      message.error('获取人员数据失败');
      setData([]);
    }
  }, [id]);

  const fetchPositions = useCallback(async () => {
    try {
      const response = await getPositions();
      if (Array.isArray(response)) {
        setPositions(response);
      } else if (response && Array.isArray(response.results)) {
        setPositions(response.results);
      } else {
        setPositions([]);
        console.log('Unexpected API response structure for positions:', response);
      }
    } catch (error) {
      message.error('获取职位数据失败');
      setPositions([]);
    } finally {
      setPositionsLoaded(true);
    }
  }, []);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  useEffect(() => {
    if (positionsLoaded) {
      fetchData(pagination.current, pagination.pageSize, searchQuery, positionFilter);
    }
  }, [positionsLoaded, id, pagination, searchQuery, positionFilter, fetchData]);

  const handleTableChange = (newPagination) => {
    setPagination(prev => ({ ...prev, current: newPagination.current, pageSize: newPagination.pageSize }));
  };

  const showCreateModal = () => {
    form.resetFields();
    setEditingId(null);
    setIsModalVisible(true);
  };

  const showEditModal = (record) => {
    form.setFieldsValue({
      ...record,
      position: record.position,
    });
    setEditingId(record.id);
    setIsModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const dataToSend = { ...values };

      if (editingId) {
        await updatePersonnel(editingId, dataToSend);
        message.success('更新成功');
      } else {
        await createPersonnel(dataToSend);
        message.success('创建成功');
      }
      setIsModalVisible(false);
      // After a successful action, reset to the first page and clear filters
      // to ensure the user sees the newly created/updated item.
      setSearchQuery('');
      setPositionFilter(null);
      if (pagination.current !== 1) {
        setPagination(prev => ({ ...prev, current: 1 }));
      } else {
        // If we are already on page 1, the pagination change won't trigger the effect,
        // so we need to trigger the refetch manually.
        fetchData(1, pagination.pageSize, '', null);
      }
    } catch (error) {
      console.error('操作失败:', error);
      message.error('操作失败');
    }
  };

  const handleDelete = (id) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该人员信息吗？',
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deletePersonnel(id);
          message.success('删除成功');
          fetchData(pagination.current, pagination.pageSize, searchQuery, positionFilter);
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };


  return (
    <div className='p-4'>
      <h2 className='text-xl font-bold mb-4'>人员管理系统</h2>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            label: '人员管理',
            key: 'personnel',
            children: (
              <>
                <div className='mb-4 flex justify-between'>
                  <Space.Compact>
                    <Input placeholder="按姓名搜索" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} style={{ width: 200 }} allowClear />
                    <Button type="primary" onClick={() => setPagination(prev => ({ ...prev, current: 1 }))}>搜索</Button>
                    <Select placeholder="按职位筛选" data-testid="personnel-position-filter" value={positionFilter} onChange={value => { setPositionFilter(value); setPagination(prev => ({ ...prev, current: 1 })); }} style={{ width: 200 }} allowClear>
                      {positions.map(pos => <Option key={pos.id} value={pos.id}>{pos.name}</Option>)}
                    </Select>
                  </Space.Compact>
                  <Button type="primary" icon={<PlusOutlined />} onClick={showCreateModal} data-testid="add-personnel-button">新增人员</Button>
                </div>
                <Table columns={columns} dataSource={Array.isArray(data) ? data : []} rowKey="id" bordered pagination={pagination} onChange={handleTableChange} />
              </>
            ),
          },
          {
            label: '职位管理',
            key: 'positions',
            children: <PositionManagementTab />,
          },
        ]}
      />

      <Modal title={editingId ? '编辑人员' : '新增人员'} open={isModalVisible} onOk={handleSubmit} onCancel={() => setIsModalVisible(false)} width={1000} destroyOnHidden data-testid="personnel-modal" okButtonProps={{ 'data-testid': 'personnel-modal-ok-button' }}>
        <Form form={form} layout="vertical">
          <Form.Item label="姓名" name="name" rules={[{ required: true }]}><Input data-testid="personnel-modal-name-input" /></Form.Item>
          <Form.Item label="职位" name="position" rules={[{ required: true }]}>
            <Select data-testid="personnel-modal-position-select" placeholder="请选择职位">
              {positions.map(pos => (
                <Option key={pos.id} value={pos.id}>{pos.name}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item label="部门" name="department"><Input /></Form.Item>
          <Form.Item label="联系电话" name="phone_number"><Input /></Form.Item>
          <Form.Item label="员工状态" name="status" initialValue="active">
            <Select>
              <Option value="active">在职</Option>
              <Option value="inactive">离职</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

    </div>
  );
};

export default PersonnelManagementPage;