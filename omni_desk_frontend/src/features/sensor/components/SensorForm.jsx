import React, { useEffect } from 'react';
import { Form, Input, Select, message } from 'antd';
import { useQuery } from 'react-query';
import { getSensorCategories, getStorageLocations } from '../api/sensorApi';

const { Option } = Select;

const SensorForm = ({ form, initialValues }) => {
  const { data: categories = [], isLoading: categoriesLoading } = useQuery('sensorCategories', getSensorCategories);
  const { data: locations = [], isLoading: locationsLoading } = useQuery('storageLocations', getStorageLocations, { select: data => data.data });

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue(initialValues);
    } else {
      form.resetFields();
    }
  }, [form, initialValues]);

  return (
    <Form form={form} layout="vertical" name="sensor_form">
      <Form.Item
        name="name"
        label="名称"
        rules={[{ required: true, message: '请输入传感器名称!' }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="category"
        label="类别"
        rules={[{ required: true, message: '请选择传感器类别!' }]}
      >
        <Select loading={categoriesLoading} placeholder="选择类别">
          {Array.isArray(categories) && categories.map(category => (
            <Option key={category.id} value={category.id}>{category.name}</Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item
        name="storage_location"
        label="存放地点"
        rules={[{ required: true, message: '请选择存放地点!' }]}
      >
        <Select loading={locationsLoading} placeholder="选择存放地点">
          {Array.isArray(locations) && locations.map(location => (
            <Option key={location.id} value={location.id}>{location.name}</Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item
        name="status"
        label="状态"
        rules={[{ required: true, message: '请选择传感器状态!' }]}
      >
        <Select placeholder="选择状态">
          <Option value="正常">正常</Option>
          <Option value="需校准">需校准</Option>
          <Option value="维修中">维修中</Option>
        </Select>
      </Form.Item>
    </Form>
  );
};

export default SensorForm;