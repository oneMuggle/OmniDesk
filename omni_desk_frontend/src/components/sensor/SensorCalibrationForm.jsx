import React, { useState } from 'react';
import { Form, Input, Button, DatePicker, Table, Space, InputNumber } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';

const SensorCalibrationForm = ({ onSubmit, onCancel }) => {
    const [form] = Form.useForm();
    const [dataPoints, setDataPoints] = useState([
        { key: 0, pressure_value: null, positive_trip_voltage_1: null, positive_trip_voltage_2: null, positive_trip_voltage_3: null, negative_trip_voltage_1: null, negative_trip_voltage_2: null, negative_trip_voltage_3: null }
    ]);

    const handleFinish = (values) => {
        const finalValues = {
            ...values,
            calibration_date: values.calibration_date.format('YYYY-MM-DD'),
            data_points: dataPoints,
        };
        onSubmit(finalValues);
    };

    const addDataPoint = () => {
        const newDataPoint = {
            key: dataPoints.length,
            pressure_value: '',
            positive_trip_voltage_1: '',
            positive_trip_voltage_2: '',
            positive_trip_voltage_3: '',
            negative_trip_voltage_1: '',
            negative_trip_voltage_2: '',
            negative_trip_voltage_3: '',
        };
        setDataPoints([...dataPoints, newDataPoint]);
    };

    const removeDataPoint = (key) => {
        const newDataPoints = dataPoints.filter(item => item.key !== key);
        setDataPoints(newDataPoints);
    };

    const handleDataPointChange = (key, field, value) => {
        const newDataPoints = dataPoints.map(item =>
            item.key === key ? { ...item, [field]: value } : item
        );
        setDataPoints(newDataPoints);
    };

    const dataPointColumns = [
        {
            title: '压力值',
            dataIndex: 'pressure_value',
            key: 'pressure_value',
            render: (text, record) => <InputNumber value={text} onChange={value => handleDataPointChange(record.key, 'pressure_value', value)} placeholder="输入压力值" />
        },
        {
            title: '正行程电压 1',
            dataIndex: 'positive_trip_voltage_1',
            key: 'positive_trip_voltage_1',
            render: (text, record) => <InputNumber value={text} onChange={value => handleDataPointChange(record.key, 'positive_trip_voltage_1', value)} />
        },
        {
            title: '正行程电压 2',
            dataIndex: 'positive_trip_voltage_2',
            key: 'positive_trip_voltage_2',
            render: (text, record) => <InputNumber value={text} onChange={value => handleDataPointChange(record.key, 'positive_trip_voltage_2', value)} />
        },
        {
            title: '正行程电压 3',
            dataIndex: 'positive_trip_voltage_3',
            key: 'positive_trip_voltage_3',
            render: (text, record) => <InputNumber value={text} onChange={value => handleDataPointChange(record.key, 'positive_trip_voltage_3', value)} />
        },
        {
            title: '负行程电压 1',
            dataIndex: 'negative_trip_voltage_1',
            key: 'negative_trip_voltage_1',
            render: (text, record) => <InputNumber value={text} onChange={value => handleDataPointChange(record.key, 'negative_trip_voltage_1', value)} />
        },
        {
            title: '负行程电压 2',
            dataIndex: 'negative_trip_voltage_2',
            key: 'negative_trip_voltage_2',
            render: (text, record) => <InputNumber value={text} onChange={value => handleDataPointChange(record.key, 'negative_trip_voltage_2', value)} />
        },
        {
            title: '负行程电压 3',
            dataIndex: 'negative_trip_voltage_3',
            key: 'negative_trip_voltage_3',
            render: (text, record) => <InputNumber value={text} onChange={value => handleDataPointChange(record.key, 'negative_trip_voltage_3', value)} />
        },
        {
            title: '操作',
            key: 'action',
            render: (_, record) =>
                dataPoints.length > 1 ? (
                    <MinusCircleOutlined onClick={() => removeDataPoint(record.key)} />
                ) : null,
        },
    ];


    return (
        <Form form={form} layout="vertical" onFinish={handleFinish}>
            <Form.Item name="calibration_instrument" label="校准仪器" rules={[{ required: true, message: '请输入校准仪器' }]}>
                <Input />
            </Form.Item>
            <Form.Item name="calibration_range" label="校准范围" rules={[{ required: true, message: '请输入校准范围' }]}>
                <Input />
            </Form.Item>
            <Form.Item name="calibration_date" label="校准日期" rules={[{ required: true, message: '请选择校准日期' }]}>
                <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="non_linearity" label="非线性度">
                <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="hysteresis" label="迟滞">
                <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="resonant_frequency" label="共振频率">
                <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="repeatability" label="重复性">
                <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="accuracy" label="精度">
                <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="rise_time" label="上升时间">
                <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="sensitivity" label="灵敏度">
                <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="calibration_equation" label="校准方程">
                <Input.TextArea />
            </Form.Item>
            <Form.Item name="remarks" label="备注">
                <Input.TextArea />
            </Form.Item>

            <h3>校准数据点</h3>
            <Table
                dataSource={dataPoints}
                columns={dataPointColumns}
                pagination={false}
                bordered
            />
            <Button type="dashed" onClick={addDataPoint} style={{ width: '100%', marginTop: '10px' }} icon={<PlusOutlined />}>
                添加数据点
            </Button>

            <Form.Item style={{ marginTop: '20px' }}>
                <Space>
                    <Button type="primary" htmlType="submit">
                        保存
                    </Button>
                    <Button onClick={onCancel}>
                        取消
                    </Button>
                </Space>
            </Form.Item>
        </Form>
    );
};

export default SensorCalibrationForm;