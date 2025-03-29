import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  fetchTrials, createTrial, updateTrial, deleteTrial,
  getEquipmentList, getResponsiblePersons,
  getEquipmentOptions, getPersonnelOptions // 保持向后兼容
} from '../api/trials';
import {
  Table, Button, Modal, Form, Input, DatePicker, Select, Upload, message
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
    select: response => Array.isArray(response.data) ? response.data : []
  });
  const { data: equipments } = useQuery({ 
    queryKey: ['equipments'],
    queryFn: getEquipmentOptions
  });
  const { data: responsiblePersons } = useQuery({ 
    queryKey: ['responsiblePersons'],
    queryFn: getPersonnelOptions
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
          onClick={() => window.open('/api/export-experiments/?format=xlsx')}
        >
          导出Excel
        </Button>
      </div>

      <Table 
        dataSource={trials} 
        rowKey="id"
        pagination={{ pageSize: 8 }}
      >
        <Column title="试验名称" dataIndex="name" key="name" />
        <Column 
          title="试验设备" 
          render={(_, record) => (record.related_equipment || []).map(e => e.name).join(', ')}
        />
        <Column title="委托单位" dataIndex="client" />
        <Column 
          title="预计完成时间" 
          render={(_, record) => dayjs(record.due_date).format('YYYY-MM-DD')}
        />
        <Column
          title="操作"
          render={(_, record) => (
            <div className="action-buttons">
              <Button type="link" onClick={() => {
                setCurrentRecord(record);
                setIsModalVisible(true);
              }}>
                编辑
              </Button>
              <Button 
                type="link" 
                danger
              onClick={() => deleteTrial(record.id)}
              >
                删除
              </Button>
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
            name="name"
            rules={[{ required: true, message: '请输入试验名称' }]}
          >
            <Input />
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
                  {equipment.name} ({equipment.model_number})
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
                  {person.name} - {person.department} ({person.position})
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="预计完成时间"
            name="due_date"
            rules={[{ required: true, message: '请选择完成时间' }]}
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
