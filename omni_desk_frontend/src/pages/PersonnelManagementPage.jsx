import React, { useState, useEffect, useCallback } from 'react';
import { Table, Button, Form, Input, Modal, message, Select, Tabs, Space } from 'antd'; // Add Select, Tabs, Space
import ConfirmModal from '../components/Calendar/ConfirmModal';
import {
  getPersonnel,
  createPersonnel,
  updatePersonnel,
  deletePersonnel,
  getPositions,
  createPosition, // Import new position APIs
  updatePosition,
  deletePosition
} from '../api/personnelApi';
import { PlusOutlined, EditOutlined, DeleteOutlined, MinusCircleOutlined, PlusCircleOutlined } from '@ant-design/icons';
import PositionManagementTab from '../components/Personnel/PositionManagementTab';

const { Option } = Select; // Destructure Option from Select

const PersonnelManagementPage = () => {
  const [form] = Form.useForm();
  const [data, setData] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [positions, setPositions] = useState([]); // New state for positions
  const [searchQuery, setSearchQuery] = useState('');
  const [positionFilter, setPositionFilter] = useState(null);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });
  const [isDeleteConfirmVisible, setIsDeleteConfirmVisible] = useState(false);
  const [selectedPersonnelId, setSelectedPersonnelId] = useState(null);

  const columns = [
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '职位',
      dataIndex: 'position_name', // Change to position_name
      key: 'position_name',
    },
    {
      title: '联系电话',
      dataIndex: 'phone_numbers',
      key: 'phone_numbers',
      render: (phone_numbers) => phone_numbers.map(p => p.number).join(', '),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <div className='space-x-2'>
          <Button
            type="primary"
            icon={<EditOutlined />}
            onClick={() => showEditModal(record)}
            data-testid={`edit-personnel-button-${record.id}`}
          >
            编辑
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
            data-testid={`delete-personnel-button-${record.id}`}
          >
            删除
          </Button>
        </div>
      ),
    },
  ];

  const fetchData = useCallback(async (params = {}) => {
    try {
      const { page = 1, pageSize = 10, search = searchQuery, position = positionFilter } = params;
      const response = await getPersonnel({
        page,
        page_size: pageSize,
        search: search,
        position: position,
      });
      
      setData(response.results); // Adjust for pagination structure
      setPagination(prev => ({
        ...prev,
        total: response.count, // Adjust for pagination structure
        current: page,
        pageSize: pageSize,
      }));
    } catch (error) {
      message.error('获取人员数据失败');
      setData([]);
    }
  }, [searchQuery, positionFilter]);

  const fetchPositions = useCallback(async () => {
    try {
      const response = await getPositions();
      setPositions(response.results || response); // Assume response.results is the array, or response itself if it's directly an array
    } catch (error) {
      message.error('获取职位数据失败');
      setPositions([]);
    }
  }, []);

  useEffect(() => {
    fetchData({
      page: pagination.current,
      pageSize: pagination.pageSize
    });
    fetchPositions(); // Fetch positions on component mount
  }, [fetchData, fetchPositions, pagination.current, pagination.pageSize]);

  const handleTableChange = (newPagination) => {
    fetchData({
      page: newPagination.current,
      pageSize: newPagination.pageSize,
      search: searchQuery,
      position: positionFilter,
    });
  };

  const showCreateModal = () => {
    form.resetFields();
    setEditingId(null);
    setIsModalVisible(true);
  };

  const showEditModal = (record) => {
    console.log('Record:', record);
    form.setFieldsValue({
      ...record,
      position: record.position || null, // Directly use position ID
      phone_numbers: record.phone_numbers || [], // 初始化 phone_numbers
    });
    setEditingId(record.id);
    setIsModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      // Directly use 'position' field from form, which will be the ID
      const dataToSend = {
        ...values,
        position: form.getFieldValue('position'),
      };
      // No need for position_id mapping or deletion

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
      console.error('操作失败:', error); // Log error for debugging
      message.error('操作失败');
    }
  };

  const handleConfirmDelete = async () => {
    if (!selectedPersonnelId) return;
    try {
      await deletePersonnel(selectedPersonnelId);
      message.success('删除成功');
      // After successful deletion, filter out the deleted item from the local state
      const newData = data.filter(item => item.id !== selectedPersonnelId);
      setData(newData);
      // If the page becomes empty after deletion and it's not the first page, fetch the previous page
      if (newData.length === 0 && pagination.current > 1) {
        fetchData({
          page: pagination.current - 1,
          pageSize: pagination.pageSize,
        });
      } else {
        // Otherwise, refetch the current page to keep data consistent
        fetchData({
          page: pagination.current,
          pageSize: pagination.pageSize,
        });
      }
    } catch (error) {
      message.error('删除失败，请稍后重试。');
    } finally {
      setIsDeleteConfirmVisible(false);
      setSelectedPersonnelId(null);
    }
  };

  const handleDelete = (id) => {
    setSelectedPersonnelId(id);
    setIsDeleteConfirmVisible(true);
  };

  const [activeTab, setActiveTab] = useState('personnel'); // New state for active tab


  return (
    <div className='p-4' data-testid="personnel-page">
      <h2 className='text-xl font-bold mb-4'>人员管理系统</h2> {/* Moved outside Tabs */}
      <Tabs
        defaultActiveKey="personnel"
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            label: '人员管理',
            key: 'personnel',
            "data-testid": "personnel-tab",
            children: (
              <>
                <div className='mb-4 flex justify-between'>
                  <Space>
                    <Input.Search
                      placeholder="按姓名搜索"
                      onSearch={(value) => {
                        setSearchQuery(value);
                        fetchData({ page: 1, pageSize: pagination.pageSize, search: value, position: positionFilter });
                      }}
                      style={{ width: 200 }}
                      allowClear
                      data-testid="personnel-search-input"
                    />
                    <Select
                      placeholder="按职位筛选"
                      onChange={(value) => {
                        setPositionFilter(value);
                        fetchData({ page: 1, pageSize: pagination.pageSize, search: searchQuery, position: value });
                      }}
                      style={{ width: 200 }}
                      allowClear
                      data-testid="personnel-position-filter"
                      getPopupContainer={(triggerNode) => triggerNode.parentNode}
                    >
                      {positions.map(pos => (
                        <Option key={pos.id} value={pos.id}>{pos.name}</Option>
                      ))}
                    </Select>
                  </Space>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={showCreateModal}
                    data-testid="add-personnel-button"
                  >
                    新增人员
                  </Button>
                </div>
                <Table
                  columns={columns}
                  dataSource={data || []}
                  rowKey="id"
                  bordered
                  pagination={{
                    ...pagination,
                    showSizeChanger: true,
                    pageSizeOptions: ['10', '20', '50'],
                    showTotal: (total) => `共 ${total} 条`,
                  }}
                  onChange={handleTableChange}
                  data-testid="personnel-table"
                />
                <Modal
                  title={editingId ? '编辑人员' : '新增人员'}
                  open={isModalVisible}
                  onOk={handleSubmit}
                  onCancel={() => setIsModalVisible(false)}
                  destroyOnClose
                  data-testid="personnel-modal"
                  footer={[
                    <Button key="back" onClick={() => setIsModalVisible(false)}>
                      取消
                    </Button>,
                    <Button key="submit" type="primary" onClick={handleSubmit} data-testid="personnel-modal-ok-button">
                      确定
                    </Button>,
                  ]}
                >
                  <Form form={form} layout="vertical">
                    <Form.Item
                      label="姓名"
                      name="name"
                      rules={[{ required: true, message: '请输入姓名' }]}
                    >
                      <Input placeholder="请输入姓名" data-testid="personnel-modal-name-input" />
                    </Form.Item>
                    <Form.Item
                      label="职位"
                      name="position"
                      rules={[{ required: true, message: '请选择职位' }]}
                    >
                      <Select
                        placeholder="请选择职位"
                        allowClear
                        data-testid="personnel-modal-position-select"
                        getPopupContainer={(triggerNode) => triggerNode.parentNode}
                        onChange={(value) => form.setFieldsValue({ position: value })}
                      >
                        {positions.map(pos => (
                          <Option key={pos.id} value={pos.id}>{pos.name}</Option>
                        ))}
                      </Select>
                    </Form.Item>
                    <Form.List name="phone_numbers">
                      {(fields, { add, remove }) => (
                        <>
                          {fields.map(({ key, name, ...restField }) => (
                            <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                              <Form.Item
                                {...restField}
                                name={[name, 'number']}
                                rules={[
                                  { required: true, message: '请输入电话号码' },
                                  { pattern: /^(\d{5}|\d{6}|1[3-9]\d{9})$/, message: '请输入有效的电话号码（5位、6位短号或11位手机号）' }
                                ]}
                              >
                                <Input placeholder="电话号码" data-testid="personnel-modal-phone-input" />
                              </Form.Item>
                              <MinusCircleOutlined onClick={() => remove(name)} />
                            </Space>
                          ))}
                          <Form.Item>
                            <Button type="dashed" onClick={() => add()} block icon={<PlusCircleOutlined />} data-testid="personnel-modal-add-phone-button">
                              添加电话号码
                            </Button>
                          </Form.Item>
                        </>
                      )}
                    </Form.List>
                  </Form>
                </Modal>
                <ConfirmModal
                  open={isDeleteConfirmVisible}
                  title="确认删除"
                  content="确定要删除该人员信息吗？"
                  okText="确认"
                  cancelText="取消"
                  type="danger"
                  onOk={handleConfirmDelete}
                  onCancel={() => {
                    setIsDeleteConfirmVisible(false);
                    setSelectedPersonnelId(null);
                  }}
                  data-testid="delete-personnel-confirm-modal"
                  okButtonProps={{ "data-testid": "delete-personnel-confirm-ok-button" }}
                />
              </>
            ),
          },
          {
            label: '职位管理',
            key: 'positions',
            "data-testid": "positions-tab",
            children: <PositionManagementTab />,
          },
        ]}
      />
    </div>
  );
};

export default PersonnelManagementPage;