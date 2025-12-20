import React, { useEffect } from 'react';
import { Form, Input, Button, InputNumber } from 'antd';

const SensorForm = ({ form, initialValues, onSubmit }) => {
  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue(initialValues);
    } else {
      form.resetFields();
    }
  }, [initialValues, form]);

  const onFinish = (values) => {
    onSubmit(values);
  };

  return (
    <Form form={form} layout="vertical" onFinish={onFinish} initialValues={initialValues}>
      <Form.Item
        name="name"
        label="传感器名称"
        rules={[{ required: true, message: '请输入传感器名称！' }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="room_temperature"
        label="室温 (°C)"
        rules={[{ required: true, message: '请输入室温！' }]}
      >
        <InputNumber style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item
        name="relative_humidity"
        label="相对湿度 (%)"
        rules={[{ required: true, message: '请输入相对湿度！' }]}
      >
        <InputNumber style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item
        name="sensor_number"
        label="传感器编号"
        rules={[{ required: true, message: '请输入传感器编号！' }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="serial_number"
        label="序列号"
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="manufacturer"
        label="制造商"
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="calibration_accuracy"
        label="校准精度"
      >
        <Input />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit">
          保存
        </Button>
      </Form.Item>
    </Form>
  );
};

export default SensorForm;