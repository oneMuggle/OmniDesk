import React, { useState, useEffect, useCallback } from 'react';
import { Table, Button, Form, Input, Modal, message, Select, Tabs, Space, DatePicker, Card, Row, Col } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, MinusCircleOutlined } from '@ant-design/icons';
import ConfirmModal from '../components/Calendar/ConfirmModal';
import { Link } from 'react-router-dom';
import {
  getPersonnel,
  createPersonnel,
  updatePersonnel,
  deletePersonnel,
  getPositions,
} from '../api/personnelApi';
import PositionManagementTab from '../components/Personnel/PositionManagementTab';

const { Option } = Select;

const PersonnelManagementPage = () => {
  const [form] = Form.useForm();
  const [data, setData] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [positions, setPositions] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [positionFilter, setPositionFilter] = useState(null);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });
  const [isDeleteConfirmVisible, setIsDeleteConfirmVisible] = useState(false);
  const [selectedPersonnelId, setSelectedPersonnelId] = useState(null);
  const [activeTab, setActiveTab] = useState('personnel');

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name' },
    { title: '职位', dataIndex: 'position', key: 'position' },
    { title: '联系电话', dataIndex: 'phone_number', key: 'phone_number' },
    { title: '部门', dataIndex: 'department', key: 'department' },
    { title: '员工状态', dataIndex: 'status', key: 'status' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Link to={`/admin/personnel/${record.id}`}>
            <Button>详情</Button>
          </Link>
          <Link to={`/admin/personnel/edit/${record.id}`}>
            <Button type="primary" icon={<EditOutlined />} />
          </Link>
          <Button danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)} />
        </Space>
      ),
    },
  ];

  const fetchData = useCallback(async (params = {}) => {
    try {
      const { page = 1, pageSize = 10, search = searchQuery, position = positionFilter } = params;
      const response = await getPersonnel({ page, page_size: pageSize, search, position });
      setData(response.results);
      setPagination(prev => ({ ...prev, total: response.count, current: page, pageSize }));
    } catch (error) {
      message.error('获取人员数据失败');
      setData([]);
    }
  }, [searchQuery, positionFilter]);

  const fetchPositions = useCallback(async () => {
    try {
      const response = await getPositions();
      setPositions(response.results || []);
    } catch (error) {
      message.error('获取职位数据失败');
      setPositions([]);
    }
  }, []);

  useEffect(() => {
    fetchData({ page: pagination.current, pageSize: pagination.pageSize });
    fetchPositions();
  }, [fetchData, fetchPositions, pagination.current, pagination.pageSize]);

  const handleTableChange = (newPagination) => {
    fetchData({ page: newPagination.current, pageSize: newPagination.pageSize });
  };

  const showCreateModal = () => {
    form.resetFields();
    setEditingId(null);
    setIsModalVisible(true);
  };

  const showEditModal = (record) => {
    form.setFieldsValue({
      ...record,
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
      fetchData();
    } catch (error) {
      console.error('操作失败:', error);
      message.error('操作失败');
    }
  };

  const handleConfirmDelete = async () => {
    if (!selectedPersonnelId) return;
    try {
      await deletePersonnel(selectedPersonnelId);
      message.success('删除成功');
      fetchData({ page: pagination.current, pageSize: pagination.pageSize });
    } catch (error) {
      message.error('删除失败');
    } finally {
      setIsDeleteConfirmVisible(false);
      setSelectedPersonnelId(null);
    }
  };

  const handleDelete = (id) => {
    setSelectedPersonnelId(id);
    setIsDeleteConfirmVisible(true);
  };


  return (
    <div className='p-4'>
      <h2 className='text-xl font-bold mb-4'>人员管理系统</h2>
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <Tabs.TabPane tab="人员管理" key="personnel">
          <div className='mb-4 flex justify-between'>
            <Space>
              <Input.Search placeholder="按姓名搜索" onSearch={value => { setSearchQuery(value); fetchData({ search: value }); }} style={{ width: 200 }} allowClear />
              <Select placeholder="按职位筛选" onChange={value => { setPositionFilter(value); fetchData({ position: value }); }} style={{ width: 200 }} allowClear>
                {positions.map(pos => <Option key={pos.id} value={pos.id}>{pos.name}</Option>)}
              </Select>
            </Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={showCreateModal}>新增人员</Button>
          </div>
          <Table columns={columns} dataSource={data} rowKey="id" bordered pagination={pagination} onChange={handleTableChange} />
        </Tabs.TabPane>
        <Tabs.TabPane tab="职位管理" key="positions">
          <PositionManagementTab />
        </Tabs.TabPane>
      </Tabs>

      <Modal title={editingId ? '编辑人员' : '新增人员'} open={isModalVisible} onOk={handleSubmit} onCancel={() => setIsModalVisible(false)} width={1000} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item label="姓名" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="职位" name="position"><Input /></Form.Item>
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

      <ConfirmModal open={isDeleteConfirmVisible} title="确认删除" content="确定要删除该人员信息吗？" okText="确认" cancelText="取消" type="danger" onOk={handleConfirmDelete} onCancel={() => setIsDeleteConfirmVisible(false)} />
    </div>
  );
};

export default PersonnelManagementPage;