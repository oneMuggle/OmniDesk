import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { Button, Table, Modal, Form, Input } from 'antd';
import { logger } from '../../../shared/utils/logger';

/**
 * 泛型 CRUD 子表格：统一管理列表拉取 / 新增 / 编辑 / 删除 / 弹窗表单。
 * 供人员详情页的各子表（家庭成员、职业资质等）复用，
 * 各调用方只需传入自己的 API 函数、数据列与表单字段定义。
 *
 * @param {string} title 实体名称（如「家庭成员」），用于按钮与弹窗标题
 * @param {Function} fetchApi (personnelId) => Promise，期望返回 { data: [...] }
 * @param {Function} createApi (payload) => Promise
 * @param {Function} updateApi (id, payload) => Promise
 * @param {Function} deleteApi (id) => Promise
 * @param {Array} columns 数据列定义（不含「操作」列，操作列由内部统一追加）
 * @param {Array} formFields 表单字段定义 [{ name, label, inputType }]
 * @param {number} personnelId 所属人员 ID
 */
const CrudSubTable = ({
  title,
  fetchApi,
  createApi,
  updateApi,
  deleteApi,
  columns,
  formFields,
  personnelId,
}) => {
  const [items, setItems] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [form] = Form.useForm();

  // 统一的数据拉取（初始加载与增/改/删后的重拉共用一处）
  const refetch = useCallback(async () => {
    if (!personnelId) return;
    try {
      const response = await fetchApi(personnelId);
      setItems(response?.data || []);
    } catch (error) {
      logger.error(`Failed to fetch ${title} list:`, error);
    }
  }, [fetchApi, personnelId, title]);

  useEffect(() => {
    const loadInitial = async () => {
      if (!personnelId) return;
      try {
        const response = await fetchApi(personnelId);
        setItems(response?.data || []);
      } catch (error) {
        setItems([]);
      }
    };

    loadInitial();
  }, [fetchApi, personnelId]);

  const showCreateModal = () => {
    setEditingItem(null);
    setIsModalVisible(true);
    form.resetFields();
  };

  const showEditModal = (record) => {
    setEditingItem(record);
    setIsModalVisible(true);
    form.setFieldsValue(record);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      const payload = { ...values, personnel: personnelId };
      if (editingItem) {
        await updateApi(editingItem.id, payload);
      } else {
        await createApi(payload);
      }
      // 保存成功后重拉列表（与原实现一致：不阻塞弹窗关闭）
      refetch();
      setIsModalVisible(false);
      setEditingItem(null);
    } catch (error) {
      logger.error(`Error saving ${title}:`, error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteApi(id);
      refetch();
    } catch (error) {
      logger.error(`Error deleting ${title}:`, error);
    }
  };

  const allColumns = [
    ...columns,
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <span>
          <Button type="link" onClick={() => showEditModal(record)}>编辑</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </span>
      ),
    },
  ];

  return (
    <div>
      <Button type="primary" onClick={showCreateModal} style={{ marginBottom: 16 }}>
        {`添加${title}`}
      </Button>
      <Table dataSource={Array.isArray(items) ? items : []} columns={allColumns} rowKey="id" />
      <Modal
        title={editingItem ? `编辑${title}` : `添加${title}`}
        open={isModalVisible}
        onOk={handleOk}
        onCancel={() => { setIsModalVisible(false); setEditingItem(null); }}
      >
        <Form form={form} layout="vertical">
          {formFields.map(field => (
            <Form.Item
              key={field.name}
              name={field.name}
              label={field.label}
              rules={[{ required: true, message: `请输入${field.label}` }]}
            >
              <Input type={field.inputType} />
            </Form.Item>
          ))}
        </Form>
      </Modal>
    </div>
  );
};

CrudSubTable.propTypes = {
  title: PropTypes.string.isRequired,
  fetchApi: PropTypes.func.isRequired,
  createApi: PropTypes.func.isRequired,
  updateApi: PropTypes.func.isRequired,
  deleteApi: PropTypes.func.isRequired,
  columns: PropTypes.arrayOf(PropTypes.object).isRequired,
  formFields: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    inputType: PropTypes.string,
  })).isRequired,
  personnelId: PropTypes.number.isRequired,
};

export default CrudSubTable;
