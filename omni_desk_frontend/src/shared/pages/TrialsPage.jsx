import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  fetchTrials, createTrial, updateTrial, deleteTrial,
  getEquipmentOptions, getPersonnelOptions // 保持向后兼容
} from '../api/trials';
import {
  Table, Button, Modal, Form, Input, DatePicker, Select, Upload, message, Popconfirm, Tag,
  Spin, Alert, Empty
} from 'antd';
import { UploadOutlined, DownloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import './TrialsPage.css';
import { isValidDate } from '../utils/dateUtils';

const { Column } = Table;
const { TextArea } = Input;
const { Option } = Select;

const TrialsPage = () => {
  const [form] = Form.useForm();
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingTrial, setEditingTrial] = useState(null);
  const queryClient = useQueryClient();


  // 获取数据 (已重构为 v5 API)
  const trialsQuery = useQuery({
    queryKey: ['trials'],
    queryFn: fetchTrials,
    select: (data) => {
      if (Array.isArray(data)) return data;
      if (data?.results && Array.isArray(data.results)) return data.results;
      return [];
    },
  });
  const { data: trials = [] } = trialsQuery;

  const equipmentsQuery = useQuery({
    queryKey: ['equipments'],
    queryFn: () => getEquipmentOptions({ page: 1, pageSize: 100 }),
    select: response => response?.results || []
  });
  const { data: equipments } = equipmentsQuery;

  const responsiblePersonsQuery = useQuery({
    queryKey: ['responsiblePersons'],
    queryFn: () => getPersonnelOptions({ page: 1, pageSize: 100 }),
    select: response => response?.results || [],
  });
  const { data: responsiblePersons } = responsiblePersonsQuery;


  // 创建/更新操作 (已重构为 v5 API)
  const trialMutation = useMutation({
    mutationFn: (values) => {
      const processedValues = {
        ...values,
        responsible_person_ids: values.responsible_persons,
        equipment_ids: values.equipment_ids,
        start_date: dayjs(values.start_date).toISOString(),
        end_date: dayjs(values.end_date).toISOString(),
        status: values.status || 'planned',
        _legacy_related_equipment: values.related_equipment
      };
      const action = editingTrial
        ? updateTrial(editingTrial.id, processedValues)
        : createTrial(processedValues);
      return action;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trials'] });
      setIsModalVisible(false);
      form.resetFields();
      message.success('操作成功');
    },
    onError: (error) => {
      message.error(`操作失败: ${error.response?.data?.message || error.message}`);
    }
  });

  // 删除操作 (已重构为 v5 API)
  const deleteMutation = useMutation({
    mutationFn: deleteTrial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trials'] });
      message.success('删除成功');
    },
    onError: (error) => {
      message.error(`删除失败: ${error.response?.data?.message || error.message}`);
    },
  });

  // 文件上传配置
  const uploadProps = {
    multiple: true,
    showUploadList: false,
    beforeUpload: file => {
      const isLt50M = file.size / 1024 / 1024 < 50;
      if (!isLt50M) {
        message.error('文件大小不能超过50MB');
        return false;
      }
      return true;
    },
  };

  if (trialsQuery.error) return <div style={{ padding: 20 }}><Alert
    message="数据加载错误"
    description={`错误详情：${trialsQuery.error.message}`}
    type="error"
    showIcon
  /></div>;

  return (
    <Spin spinning={trialsQuery.isLoading} tip="加载试验数据中...">
      <div className="trials-container">
      <div className="header-section">
        <Button
          type="primary"
          onClick={() => {
            setEditingTrial(null);
            form.resetFields(); // 确保在打开新建模态框时表单是干净的
            setIsModalVisible(true);
          }}
        >
          新建试验
        </Button>
        <Button
          icon={<DownloadOutlined />}
          onClick={() => window.open('/api/export-trials/?format=xlsx')}
        >
          导出Excel
        </Button>
      </div>

      <Table
        dataSource={trials ?? []}
        rowKey="id"
        pagination={{ pageSize: 8 }}
        locale={{
          emptyText: <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={trials ? "暂无试验数据" : "数据加载失败"}
          />
        }}
      >
        <Column title="试验名称" dataIndex="title" key="title" />
        <Column
          title="试验设备"
          render={(_, record) => (record.equipments || []).map(e => e?.name || '未知设备').join(', ') || '暂无设备'}
        />
        <Column title="委托单位" dataIndex="client" key="client" />
        <Column
          title="负责人"
          render={(_, record) => (record.responsible_persons || []).map(p => (
            <a href={`tel:${p?.phone}`} key={p.id}>
              {p?.name || '未知人员'}
            </a>
          )).reduce((prev, curr) => [prev, ' ', curr], []) || '无'}
        />
        <Column
          title="状态"
          render={(_, record) => (
            <Tag color={
              {
                planned: 'blue',
                in_progress: 'green',
                completed: 'gray',
                cancelled: 'red'
              }[record.status]
            }>
              {{
                planned: '计划中',
                in_progress: '进行中',
                completed: '已完成',
                cancelled: '已取消'
              }[record.status]}
            </Tag>
          )}
        />
        <Column
          title="开始时间"
          render={(_, record) => {
            try {
              const date = dayjs(record.start_date);
              return isValidDate(date) ? date.format('YYYY-MM-DD') : '无效日期';
            } catch (e) {
              return '无效日期';
            }
          }}
        />
        <Column
          title="结束时间"
          render={(_, record) => {
            try {
              const date = dayjs(record.end_date);
              return isValidDate(date) ? date.format('YYYY-MM-DD') : '无效日期';
            } catch (e) {
              return '无效日期';
            }
          }}
        />
        <Column
          title="操作"
          render={(_, record) => (
            <div className="action-buttons">
              <Button
                type="link"
                onClick={() => {
                  const processedRecord = {
                    ...record,
                    start_date: record.start_date ? dayjs(record.start_date) : null,
                    end_date: record.end_date ? dayjs(record.end_date) : null,
                    equipment_ids: record.equipments?.map(e => e.id),
                    responsible_persons: record.responsible_persons?.map(p => p.id),
                  };
                  setEditingTrial(processedRecord);
                  setIsModalVisible(true);
                }}
                style={{ padding: '0 8px' }}
              >
                编辑
              </Button>
              <Popconfirm
                title="确认删除该试验？"
                onConfirm={() => deleteMutation.mutate(record.id)}
                okText="确定"
                cancelText="取消"
                disabled={deleteMutation.isPending}
              >
                <Button
                  type="link"
                  danger
                  style={{ padding: '0 8px' }}
                >
                  删除
                </Button>
              </Popconfirm>
            </div>
          )}
        />
      </Table>

      <Modal
        title={editingTrial ? '编辑试验' : '新建试验'}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={null}
        destroyOnHidden // 使用 destroyOnHidden 确保每次关闭时销毁子元素
      >
        <Form
          key={editingTrial ? editingTrial.id : 'new'}
          form={form}
          initialValues={editingTrial}
          onFinish={trialMutation.mutate}
          layout="vertical"
        >
          <Form.Item
            label="试验名称"
            name="title"
            rules={[{ required: true, message: '请输入试验名称' }]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            label="试验描述"
            name="description"
            rules={[{ required: true, message: '请输入试验描述' }]}
          >
            <TextArea rows={2} />
          </Form.Item>

          <Form.Item
            label="试验设备"
            name="equipment_ids"
            rules={[{ required: true, message: '请选择试验设备' }]}
          >
            <Select
              mode="multiple"
              placeholder="请选择试验设备"
              loading={equipmentsQuery.isLoading}
              optionFilterProp="children"
              showSearch
            >
              {equipments?.map(equipment => (
                <Option
                  key={equipment.id}
                  value={equipment.id}
                  title={`设备编号：${equipment.serial_number}`}
                >
                  {`${equipment.name}${equipment.description ? ` (${equipment.description})` : ''}`}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="委托单位"
            name="client"
            rules={[{ required: true, message: '请输入委托单位' }]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            label="状态"
            name="status"
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="planned">计划中</Option>
              <Option value="in_progress">进行中</Option>
              <Option value="completed">已完成</Option>
              <Option value="cancelled">已取消</Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="负责人"
            name="responsible_persons"
            rules={[{ required: true, message: '请选择负责人' }]}
          >
            <Select
              mode="multiple"
              placeholder="请选择负责人"
              loading={responsiblePersonsQuery.isLoading}
              optionFilterProp="children"
              showSearch
              filterOption={(input, option) =>
                (option?.children ?? '').toLowerCase().includes(input.toLowerCase())
              }
            >
              {responsiblePersons?.map(person => (
                <Option
                  key={person.id}
                  value={person.id}
                  title={`联系方式：${person.phone}`}
                >
                  {`${person.name}${person.department ? ` - ${person.department}` : ''}`}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="开始时间"
            name="start_date"
            rules={[{ required: true, message: '请选择开始时间' }]}
          >
            <DatePicker format="YYYY-MM-DD" style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            label="结束时间"
            name="end_date"
            rules={[{ required: true, message: '请选择结束时间' }]}
          >
            <DatePicker format="YYYY-MM-DD" style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item label="备注" name="remarks">
            <TextArea rows={4} />
          </Form.Item>

          <Form.Item label="上传附件">
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={trialMutation.isPending}>
              {editingTrial ? '更新' : '创建'}
            </Button>
          </Form.Item>
        </Form>
      </Modal>
      </div>
    </Spin>
  );
};

export default TrialsPage;
