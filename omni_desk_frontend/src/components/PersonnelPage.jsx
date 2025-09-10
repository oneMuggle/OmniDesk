import React, { useState, useEffect, useCallback } from 'react';
import { Table, Button, Form, Input, Modal, message, Select, Tabs, Space } from 'antd'; // Add Select, Tabs, Space
import ConfirmModal from './Calendar/ConfirmModal';
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

const { Option } = Select; // Destructure Option from Select
const { TabPane } = Tabs; // Destructure TabPane from Tabs

const PersonnelPage = () => {
  const [form] = Form.useForm();
  const [data, setData] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [positions, setPositions] = useState([]); // New state for positions
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });

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
          >
            编辑
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          >
            删除
          </Button>
        </div>
      ),
    },
  ];

  const fetchData = useCallback(async (params = {}) => {
    try {
      const { page = 1, pageSize = 10 } = params;
      const response = await getPersonnel({
        page,
        page_size: pageSize
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
  }, []);

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
  }, [fetchData, fetchPositions]);

  const handleTableChange = (newPagination) => {
    fetchData({
      page: newPagination.current,
      pageSize: newPagination.pageSize,
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

  const handleDelete = async (id) => {
    ConfirmModal({
      title: '确认删除',
      content: '确定要删除该人员信息吗？',
      okText: '确认',
      cancelText: '取消',
      type: 'danger',
      onConfirm: async () => {
        try {
          await deletePersonnel(id);
          message.success('删除成功');
          fetchData();
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };

  const [activeTab, setActiveTab] = useState('personnel'); // New state for active tab

  // Position Management Tab Component
  const PositionManagementTab = () => {
    const [positionForm] = Form.useForm();
    const [positionData, setPositionData] = useState([]);
    const [isPositionModalVisible, setIsPositionModalVisible] = useState(false);
    const [editingPositionId, setEditingPositionId] = useState(null);

    const fetchPositionData = useCallback(async () => {
      try {
        const response = await getPositions();
        setPositionData(response.results || response);
      } catch (error) {
        message.error('获取职位数据失败');
        setPositionData([]);
      }
    }, []);

    useEffect(() => {
      fetchPositionData();
    }, [fetchPositionData]);

    const positionColumns = [
      {
        title: '职位名称',
        dataIndex: 'name',
        key: 'name',
      },
      {
        title: '操作',
        key: 'action',
        render: (_, record) => (
          <div className='space-x-2'>
            <Button
              type="primary"
              icon={<EditOutlined />}
              onClick={() => showEditPositionModal(record)}
            >
              编辑
            </Button>
            <Button
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDeletePosition(record.id)}
            >
              删除
            </Button>
          </div>
        ),
      },
    ];

    const showCreatePositionModal = () => {
      positionForm.resetFields();
      setEditingPositionId(null);
      setIsPositionModalVisible(true);
    };

    const showEditPositionModal = (record) => {
      positionForm.setFieldsValue(record);
      setEditingPositionId(record.id);
      setIsPositionModalVisible(true);
    };

    const handleSubmitPosition = async () => {
      try {
        const values = await positionForm.validateFields();
        if (editingPositionId) {
          await updatePosition(editingPositionId, values);
          message.success('职位更新成功');
        } else {
          await createPosition(values);
          message.success('职位创建成功');
        }
        setIsPositionModalVisible(false);
        fetchPositionData();
      } catch (error) {
        message.error('职位操作失败');
      }
    };

    const handleDeletePosition = async (id) => {
      ConfirmModal({
        title: '确认删除',
        content: '确定要删除该职位吗？',
        okText: '确认',
        cancelText: '取消',
        type: 'danger',
        onConfirm: async () => {
          try {
            await deletePosition(id);
            message.success('职位删除成功');
            fetchPositionData();
          } catch (error) {
            message.error('职位删除失败');
          }
        },
      });
    };

    return (
      <div>
        <div className='mb-4 flex justify-between'>
          <h3 className='text-lg font-bold'>职位管理</h3>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={showCreatePositionModal}
          >
            新增职位
          </Button>
        </div>
        <Table
          columns={positionColumns}
          dataSource={positionData || []}
          rowKey="id"
          bordered
          pagination={false} // Positional data often doesn't need pagination
        />
        <Modal
          title={editingPositionId ? '编辑职位' : '新增职位'}
          visible={isPositionModalVisible}
          onOk={handleSubmitPosition}
          onCancel={() => setIsPositionModalVisible(false)}
          destroyOnClose
        >
          <Form form={positionForm} layout="vertical">
            <Form.Item
              label="职位名称"
              name="name"
              rules={[{ required: true, message: '请输入职位名称' }]}
            >
              <Input placeholder="请输入职位名称" />
            </Form.Item>
          </Form>
        </Modal>
      </div>
    );
  };

  return (
    <div className='p-4'>
      <h2 className='text-xl font-bold mb-4'>人员管理系统</h2> {/* Moved outside Tabs */}
      <Tabs defaultActiveKey="personnel" activeKey={activeTab} onChange={setActiveTab}>
        <TabPane tab="人员管理" key="personnel">
          <div className='mb-4 flex justify-end'> {/* Adjusted flex for button alignment */}
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={showCreateModal}
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
          />

          <Modal
            title={editingId ? '编辑人员' : '新增人员'}
            visible={isModalVisible}
            onOk={handleSubmit}
            onCancel={() => setIsModalVisible(false)}
            destroyOnClose
          >
            <Form form={form} layout="vertical">
              <Form.Item
                label="姓名"
                name="name"
                rules={[{ required: true, message: '请输入姓名' }]}
              >
                <Input placeholder="请输入姓名" />
              </Form.Item>



              <Form.Item
                label="职位"
                name="position" // Changed to 'position'
                rules={[{ required: true, message: '请选择职位' }]}
              >
                <Select placeholder="请选择职位" allowClear>
                  {positions.map(pos => (
                    <Option key={pos.id} value={pos.id}>{pos.name}</Option>
                  ))}
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
                          rules={[
                            { required: true, message: '请输入电话号码' },
                            { pattern: /^(\d{5}|\d{6}|1[3-9]\d{9})$/, message: '请输入有效的电话号码（5位、6位短号或11位手机号）' }
                          ]}
                        >
                          <Input placeholder="电话号码" />
                        </Form.Item>
                        <MinusCircleOutlined onClick={() => remove(name)} />
                      </Space>
                    ))}
                    <Form.Item>
                      <Button type="dashed" onClick={() => add()} block icon={<PlusCircleOutlined />}>
                        添加电话号码
                      </Button>
                    </Form.Item>
                  </>
                )}
              </Form.List>
            </Form>
          </Modal>
        </TabPane>
        <TabPane tab="职位管理" key="positions">
          <PositionManagementTab />
        </TabPane>
      </Tabs>
    </div>
  );
};

export default PersonnelPage;
