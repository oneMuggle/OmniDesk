import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Button, Form, Input, Modal, message } from 'antd';
import {
  getPositions,
  createPosition,
  updatePosition,
  deletePosition
} from '../api/personnelApi';
import { extractResults } from '../../../shared/api/responseHandler';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import DataTable from '../../../shared/components/DataTable';

/**
 * 职位管理 Tab（独立组件）。
 * onPositionsChanged：职位增/改/删成功后的可选回调，
 * 供父级页面同步刷新人员列表的职位列与职位下拉选项。
 */
const PositionManagementTab = ({ onPositionsChanged }) => {
  const [positionForm] = Form.useForm();
  const [positionData, setPositionData] = useState([]);
  const [isPositionModalVisible, setIsPositionModalVisible] = useState(false);
  const [editingPositionId, setEditingPositionId] = useState(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const fetchPositionData = async () => {
      try {
        const response = await getPositions();
        setPositionData(extractResults(response?.data || response));
      } catch (error) {
        message.error('获取职位数据失败');
        setPositionData([]);
      }
    };

    fetchPositionData();
  }, [version]);

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
            data-testid={`edit-position-button-${record.id}`}
          >
            编辑
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeletePosition(record.id)}
            data-testid={`delete-position-button-${record.id}`}
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
      setVersion(v => v + 1);
      onPositionsChanged?.();
    } catch (error) {
      message.error('职位操作失败');
    }
  };

  const handleDeletePosition = (id) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该职位吗？',
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deletePosition(id);
          message.success('职位删除成功');
          setVersion(v => v + 1);
          onPositionsChanged?.();
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
          data-testid="add-position-button"
        >
          新增职位
        </Button>
      </div>
      <DataTable
        columns={positionColumns}
        dataSource={Array.isArray(positionData) ? positionData : []}
        rowKey="id"
        bordered
        pagination={false} // Positional data often doesn't need pagination
        data-testid="position-table"
        showActions={false}
      />
      <Modal
        title={editingPositionId ? '编辑职位' : '新增职位'}
        open={isPositionModalVisible}
        onOk={handleSubmitPosition}
        onCancel={() => setIsPositionModalVisible(false)}
        destroyOnHidden
        data-testid="position-modal"
      >
        <Form form={positionForm} layout="vertical">
          <Form.Item
            label="职位名称"
            name="name"
            rules={[{ required: true, message: '请输入职位名称' }]}
          >
            <Input placeholder="请输入职位名称" data-testid="position-modal-name-input" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

PositionManagementTab.propTypes = {
  onPositionsChanged: PropTypes.func,
};

export default PositionManagementTab;