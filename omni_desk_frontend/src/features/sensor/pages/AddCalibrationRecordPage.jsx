import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Form,
  Input,
  DatePicker,
  Select,
  Table,
  Button,
  Card,
  Row,
  Col,
  message,
  InputNumber,
} from 'antd';
import { getSensors, createCalibrationRecord } from '../api/sensorApi';

const { Option } = Select;

const initialDataPoint = {
  key: 0,
  pressure: '',
  positive_trip_voltage_1: '',
  negative_trip_voltage_1: '',
  positive_trip_voltage_2: '',
  negative_trip_voltage_2: '',
  positive_trip_voltage_3: '',
  negative_trip_voltage_3: '',
};

const AddCalibrationRecordPage = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [sensors, setSensors] = useState([]);
  const [dataSource, setDataSource] = useState([
    { ...initialDataPoint, key: 0 },
    { ...initialDataPoint, key: 1 },
    { ...initialDataPoint, key: 2 },
    { ...initialDataPoint, key: 3 },
    { ...initialDataPoint, key: 4 },
    { ...initialDataPoint, key: 5 },
  ]);

  useEffect(() => {
    const fetchSensors = async () => {
      try {
        const response = await getSensors();
        setSensors(Array.isArray(response.data) ? response.data : response.data?.results || []);
      } catch (error) {
        message.error('获取传感器列表失败');
        console.error('Failed to fetch sensors:', error);
      }
    };
    fetchSensors();
  }, []);

  const handleTableChange = (key, field, value) => {
    const newData = [...dataSource];
    const index = newData.findIndex((item) => key === item.key);
    if (index > -1) {
      const item = newData[index];
      newData.splice(index, 1, { ...item, [field]: value });
      setDataSource(newData);
    }
  };

  const columns = [
    {
      title: '压力 (kPa/MPa)',
      dataIndex: 'pressure',
      key: 'pressure',
      render: (text, record) => (
        <InputNumber
          style={{ width: '100%' }}
          value={text}
          onChange={(value) => handleTableChange(record.key, 'pressure', value)}
        />
      ),
    },
    {
      title: '正行程输出电压 (mV)',
      children: [
        {
          title: '1',
          dataIndex: 'positive_trip_voltage_1',
          key: 'positive_trip_voltage_1',
          render: (text, record) => (
            <InputNumber
              style={{ width: '100%' }}
              value={text}
              onChange={(value) => handleTableChange(record.key, 'positive_trip_voltage_1', value)}
            />
          ),
        },
        {
          title: '2',
          dataIndex: 'positive_trip_voltage_2',
          key: 'positive_trip_voltage_2',
          render: (text, record) => (
            <InputNumber
              style={{ width: '100%' }}
              value={text}
              onChange={(value) => handleTableChange(record.key, 'positive_trip_voltage_2', value)}
            />
          ),
        },
        {
          title: '3',
          dataIndex: 'positive_trip_voltage_3',
          key: 'positive_trip_voltage_3',
          render: (text, record) => (
            <InputNumber
              style={{ width: '100%' }}
              value={text}
              onChange={(value) => handleTableChange(record.key, 'positive_trip_voltage_3', value)}
            />
          ),
        },
      ],
    },
    {
      title: '反行程输出电压 (mV)',
      children: [
        {
          title: '1',
          dataIndex: 'negative_trip_voltage_1',
          key: 'negative_trip_voltage_1',
          render: (text, record) => (
            <InputNumber
              style={{ width: '100%' }}
              value={text}
              onChange={(value) => handleTableChange(record.key, 'negative_trip_voltage_1', value)}
            />
          ),
        },
        {
          title: '2',
          dataIndex: 'negative_trip_voltage_2',
          key: 'negative_trip_voltage_2',
          render: (text, record) => (
            <InputNumber
              style={{ width: '100%' }}
              value={text}
              onChange={(value) => handleTableChange(record.key, 'negative_trip_voltage_2', value)}
            />
          ),
        },
        {
          title: '3',
          dataIndex: 'negative_trip_voltage_3',
          key: 'negative_trip_voltage_3',
          render: (text, record) => (
            <InputNumber
              style={{ width: '100%' }}
              value={text}
              onChange={(value) => handleTableChange(record.key, 'negative_trip_voltage_3', value)}
            />
          ),
        },
      ],
    },
  ];

  const onFinish = async (values) => {
    const payload = {
      ...values,
      calibration_date: values.calibration_date.format('YYYY-MM-DD'),
      data_points: dataSource,
    };
    try {
      await createCalibrationRecord(payload);
      message.success('校准记录创建成功');
      form.resetFields();
      setDataSource([
        { ...initialDataPoint, key: 0 },
        { ...initialDataPoint, key: 1 },
        { ...initialDataPoint, key: 2 },
        { ...initialDataPoint, key: 3 },
        { ...initialDataPoint, key: 4 },
        { ...initialDataPoint, key: 5 },
      ]);
    } catch (error) {
      message.error('创建校准记录失败');
      console.error('Failed to create calibration record:', error);
    }
  };

  return (
    <Card title="压力传感器校准记录">
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Row gutter={16}>
          <Col span={8}>
            <Form.Item
              name="sensor"
              label="传感器"
              rules={[{ required: true, message: '请选择一个传感器' }]}
            >
              <Select placeholder="选择一个传感器">
                {sensors.map((sensor) => (
                  <Option key={sensor.id} value={sensor.id}>
                    {sensor.name} ({sensor.sensor_id})
                  </Option>
                ))}
              </Select>
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="room_temperature" label="室温 (°C)">
              <Input />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="relative_humidity" label="相对湿度 (%)">
              <Input />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={8}>
            <Form.Item name="calibration_instrument" label="校准仪器">
              <Input />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item
              name="calibration_date"
              label="校准日期"
              rules={[{ required: true, message: '请选择校准日期' }]}
            >
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>

        <Card title="数据记录" type="inner" style={{ marginTop: 16 }}>
          <Table
            bordered
            dataSource={dataSource}
            columns={columns}
            pagination={false}
            rowKey="key"
          />
        </Card>

        <Card title="性能指标" type="inner" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="non_linearity" label="非线性度 (%)">
                <Input />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="hysteresis" label="迟滞 (%)">
                <Input />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="repeatability" label="重复性 (%)">
                <Input />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="accuracy" label="准确度 (%)">
                <Input />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        <Card title="校准信息" type="inner" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="sensitivity" label="灵敏度 (mV/V)">
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="calibration_equation" label="校准方程">
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="calibrated_by"
                label="校准人"
                rules={[{ required: true, message: '请输入校准人' }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="reviewed_by"
                label="审核人"
                rules={[{ required: true, message: '请输入审核人' }]}
              >
                <Input />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        <Form.Item style={{ marginTop: 24, textAlign: 'right' }}>
          <Button onClick={() => navigate('/sensor-management')} style={{ marginRight: 8 }}>
            返回
          </Button>
          <Button type="primary" htmlType="submit">
            提交记录
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default AddCalibrationRecordPage;