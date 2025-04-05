import React, { useState, useEffect } from 'react';
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

const { Column } = Table;
const { TextArea } = Input;
const { Option } = Select;

const TrialsPage = () => {
  const [form] = Form.useForm();
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState(null);
  const queryClient = useQueryClient();

  // 获取数据
  const { data: trials = [], isLoading, error } = useQuery({ 
    queryKey: ['trials'],
    queryFn: fetchTrials,
    select: (data) => data?.results || [],
    useErrorBoundary: true,
    retry: false,
    onError: (error) => {
      console.error('API Request Error:', error);
    },
    onSuccess: (data) => {
      console.log('Processed trials data:', data);
    }
  });
  const { data: equipments } = useQuery({ 
    queryKey: ['equipments'],
    queryFn: () => getEquipmentOptions({ page: 1, pageSize: 100 }),
    select: response => response?.results || []
  });
  const { data: responsiblePersons } = useQuery({ 
    queryKey: ['responsiblePersons'],
    queryFn: () => getPersonnelOptions({ page: 1, pageSize: 100 }),
    select: response => response?.results || [],
    onError: (error) => console.error('[MCP_ERROR] 人员选项加载失败:', error),
    onSuccess: (data) => console.log('[MCP_DEBUG] 人员选项加载完成:', data)
  });

  // 调试设备数据加载状态
  useEffect(() => {
    console.log('[MCP_DEBUG] 当前设备选项数据:', equipments);
  }, [equipments]);

  // 调试人员数据加载状态  
  useEffect(() => {
    console.log('[MCP_DEBUG] 当前人员选项数据:', responsiblePersons);
  }, [responsiblePersons]);

  // 表单提交处理
  const handleSubmit = useMutation({
    mutationFn: (values) => {
    const processedValues = {
      ...values,
      responsible_person_ids: values.responsible_persons,
      equipment_ids: values.equipment_ids,
      start_date: dayjs(values.start_date).toISOString(),
      end_date: dayjs(values.end_date).toISOString(),
      status: values.status || 'planned', // 添加默认状态
      _legacy_related_equipment: values.related_equipment
    };
      return currentRecord ? updateTrial(currentRecord.id, processedValues) : createTrial(processedValues);
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

  if (isLoading) return <div style={{ padding: 20 }}><Spin tip="加载试验数据中..." /></div>;
  if (error) return <div style={{ padding: 20 }}><Alert 
    message="数据加载错误"
    description={`错误详情：${error.message}`}
    type="error"
    showIcon
  /></div>;

  return (
    <div className="trials-container">
      {console.log('Trials Data Structure:', trials)}
      {console.log('API Response Sample:', trials?.[0])}
      <div className="header-section">
        <Button 
          type="primary" 
          onClick={() => {
            setCurrentRecord(null);
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
              // 直接解析ISO8601格式并转换时区（UTC+8）
              const date = dayjs(record.start_date);
              return date.isValid() ? date.format('YYYY-MM-DD') : '无效日期';
            } catch (e) {
              return '无效日期';
            }
          }}
        />
        <Column 
          title="结束时间" 
          render={(_, record) => {
            try {
              // 直接解析ISO8601格式并转换时区（UTC+8）
              const date = dayjs(record.end_date);
              return date.isValid() ? date.format('YYYY-MM-DD') : '无效日期';
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
                  setCurrentRecord(record);
                  setIsModalVisible(true);
                }}
                style={{ padding: '0 8px' }}
              >
                编辑
              </Button>
              <Popconfirm
                title="确认删除该试验？"
                onConfirm={async () => {
                  try {
                    await deleteTrial(record.id);
                    queryClient.invalidateQueries({ queryKey: ['trials'] });
                    message.success('删除成功');
                  } catch (error) {
                    message.error(`删除失败: ${error.response?.data?.message || error.message}`);
                  }
                }}
                okText="确定"
                cancelText="取消"
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
        title={currentRecord ? '编辑试验' : '新建试验'}
        visible={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={null}
      >
        <Form
          form={form}
          initialValues={currentRecord ? {
            ...currentRecord,
            equipment_ids: currentRecord.equipments?.map(e => e.id),
            responsible_persons: currentRecord.responsible_persons?.map(p => p.id),
            start_date: currentRecord.start_date ? dayjs(currentRecord.start_date) : dayjs(),
            end_date: currentRecord.end_date ? dayjs(currentRecord.end_date) : dayjs().add(1, 'day')
          } : {
            start_date: dayjs(),
            end_date: dayjs().add(1, 'day')
          }}
          onFinish={handleSubmit.mutate}
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
            initialValue="planned"
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
              optionFilterProp="children"
              showSearch
              filterOption={(input, option) =>
                option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
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
            <DatePicker format="YYYY-MM-DD" />
          </Form.Item>

          <Form.Item
            label="结束时间"
            name="end_date"
            rules={[{ required: true, message: '请选择结束时间' }]}
          >
            <DatePicker format="YYYY-MM-DD" />
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
            <Button type="primary" htmlType="submit">
              提交
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default TrialsPage;
