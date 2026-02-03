import PropTypes from 'prop-types';
import { Form, Input, Select } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getSensorCategories, getStorageLocations } from '../api/sensorApi';

const { Option } = Select;

const SensorForm = ({ form, initialValues }) => {
  const { data: categories = [], isPending: categoriesPending } = useQuery({
    queryKey: ['sensorCategories'],
    queryFn: () => getSensorCategories({ page_size: 1000 }),
    select: (data) => data.data.results,
  });
  const { data: locations = [], isPending: locationsPending } = useQuery({
    queryKey: ['storageLocations'],
    queryFn: () => getStorageLocations({ page_size: 1000 }),
    select: (data) => data.data.results,
  });

  return (
    <Form form={form} layout="vertical" name="sensor_form" initialValues={initialValues}>
      <Form.Item
        name="name"
        label="名称"
        rules={[{ required: true, message: '请输入传感器名称!' }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="sensor_number"
        label="传感器编号"
        rules={[{ required: true, message: '请输入传感器编号!' }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="category_id"
        label="类别"
        rules={[{ required: true, message: '请选择传感器类别!' }]}
      >
        <Select loading={categoriesPending} placeholder="选择类别">
          {Array.isArray(categories) && categories.map(category => (
            <Option key={category.id} value={category.id}>{category.name}</Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item
        name="storage_location_id"
        label="存放地点"
        rules={[{ required: true, message: '请选择存放地点!' }]}
      >
        <Select loading={locationsPending} placeholder="选择存放地点">
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
          <Option value="in_stock">在库</Option>
          <Option value="in_use">在用</Option>
          <Option value="under_calibration">校准中</Option>
          <Option value="retired">退役</Option>
        </Select>
      </Form.Item>
    </Form>
  );
};

SensorForm.propTypes = {
  form: PropTypes.object.isRequired,
  initialValues: PropTypes.object,
};

export default SensorForm;