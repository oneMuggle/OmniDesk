import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  fetchTrials, createTrial, updateTrial, deleteTrial,
  getEquipmentOptions, getPersonnelOptions // 保持向后兼容
} from '../api/trials';
import {
  Table, Button, Modal, Form, Input, DatePicker, Select, Upload, message, Popconfirm, Tag
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
  const { data: trials } = useQuery({ 
    queryKey: ['trials'],
    queryFn: fetchTrials,
    select: response => response.data?.results || []
  });
  const { data: equipments } = useQuery({ 
    queryKey: ['equipments'],
    queryFn: getEquipmentOptions,
    select: response => response.data?.results || []
  });
  const { data: responsiblePersons } = useQuery({ 
    queryKey: ['responsiblePersons'],
    queryFn: getPersonnelOptions,
    select: response => response.data?.results || []
  });

  // 表单提交处理
  const handleSubmit = useMutation({
    mutationFn: (values) => currentRecord ? updateTrial(currentRecord.id, values) : createTrial(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trials'] });
      setIsModalVisible(false);
      form.resetFields();
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

  return (
    <div className="trials-container">
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
        dataSource={trials} 
        rowKey="id"
        pagination={{ pageSize: 8 }}
      >
        <Column title="试验名称" dataIndex="title" key="title" />
        <Column 
          title="试验设备" 
          render={(_, record) => (record.related_equipment || []).map(e => e?.name || '未知设备').join(', ') || '无'}
        />
        <Column title="委托单位" dataIndex="client" />
        <Column 
          title="负责人"
          render={(_, record) => (record.responsible_persons || []).map(p => (
            <a href={`mailto:${p?.email}`} key={p.id}>
              {p?.name || '未知人员'}
            </a>
          )).reduce((prev, curr) => [prev, ', ', curr]) || '无'}
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
              const date = dayjs(record.start_date).utcOffset(480); // 480分钟 = 8小时
              return date.isValid() ? date.format('YYYY-MM-DD HH:mm') : '无效日期';
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
              const date = dayjs(record.end_date).utcOffset(480); // 480分钟 = 8小时
              return date.isValid() ? date.format('YYYY-MM-DD HH:mm') : '无效日期';
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
                onConfirm={() => deleteTrial(record.id)}
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
            related_equipment: currentRecord.related_equipment?.map(e => e.id),
            responsible_persons: currentRecord.responsible_persons?.map(p => p.id),
            due_date: dayjs(currentRecord.due_date)
          } : {}}
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
          name="related_equipment"
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
                  {equipment.name} ({equipment.description})
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
                  {person.name} - {person.department}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="开始时间"
            name="start_date"
            rules={[{ required: true, message: '请选择开始时间' }]}
          >
            <DatePicker showTime format="YYYY-MM-DD HH:mm" />
          </Form.Item>

          <Form.Item
            label="结束时间"
            name="end_date"
            rules={[{ required: true, message: '请选择结束时间' }]}
          >
            <DatePicker showTime format="YYYY-MM-DD HH:mm" />
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
