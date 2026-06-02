import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Space, Collapse } from 'antd';
import axiosInstance from '../../../shared/api/axiosConfig';
import { logger } from '../../../shared/utils/logger';

const SensorCalibrationManagementPage = () => {
    const { sensorId } = useParams();
    const [calibrations, setCalibrations] = useState([]);
    const [loading, setLoading] = useState(false);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [editingCalibration, setEditingCalibration] = useState(null);
    const [form] = Form.useForm();

    const fetchCalibrations = useCallback(async () => {
        setLoading(true);
        try {
            const response = await axiosInstance.get(`/api/sensor-management/sensor-calibrations/?sensor_id=${sensorId}`);
            setCalibrations(response.data);
        } catch (error) {
            message.error('Failed to fetch sensor calibrations.');
            logger.error('Error fetching calibrations:', error);
        } finally {
            setLoading(false);
        }
    }, [sensorId]);

    useEffect(() => {
        if (sensorId) {
            fetchCalibrations();
        }
    }, [fetchCalibrations, sensorId]);

    const handleAdd = () => {
        setEditingCalibration(null);
        form.resetFields();
        setIsModalVisible(true);
    };

    const handleEdit = (record) => {
        setEditingCalibration(record);
        form.setFieldsValue(record);
        setIsModalVisible(true);
    };

    const handleDelete = async (id) => {
        try {
            await axiosInstance.delete(`/api/sensor-management/sensor-calibrations/${id}/`);
            message.success('Calibration deleted successfully.');
            fetchCalibrations();
        } catch (error) {
            message.error('Failed to delete calibration.');
            logger.error('Error deleting calibration:', error);
        }
    };

    const handleModalOk = async () => {
        try {
            const values = await form.validateFields();
            if (editingCalibration) {
                await axiosInstance.put(`/api/sensor-management/sensor-calibrations/${editingCalibration.id}/`, values);
                message.success('Calibration updated successfully.');
            } else {
                await axiosInstance.post('/api/sensor-management/sensor-calibrations/', { ...values, sensor: sensorId });
                message.success('Calibration added successfully.');
            }
            setIsModalVisible(false);
            fetchCalibrations();
        } catch (error) {
            message.error('Failed to save calibration.');
            logger.error('Error saving calibration:', error);
        }
    };

    const handleModalCancel = () => {
        setIsModalVisible(false);
    };

    const columns = [
        { title: 'Calibration Instrument', dataIndex: 'calibration_instrument', key: 'calibration_instrument' },
        { title: 'Calibration Range', dataIndex: 'calibration_range', key: 'calibration_range' },
        { title: 'Calibration Date', dataIndex: 'calibration_date', key: 'calibration_date' },
        {
            title: 'Pressure Values',
            dataIndex: 'pressure_values',
            key: 'pressure_values',
            render: (text) => (
                <Collapse ghost>
                    <Collapse.Panel header="View Details" key="1">
                        <pre>{JSON.stringify(text, null, 2)}</pre>
                    </Collapse.Panel>
                </Collapse>
            ),
        },
        {
            title: 'Voltage Values',
            dataIndex: 'voltage_values',
            key: 'voltage_values',
            render: (text) => (
                <Collapse ghost>
                    <Collapse.Panel header="View Details" key="1">
                        <pre>{JSON.stringify(text, null, 2)}</pre>
                    </Collapse.Panel>
                </Collapse>
            ),
        },
        { title: 'Non-linearity', dataIndex: 'non_linearity', key: 'non_linearity' },
        { title: 'Hysteresis', dataIndex: 'hysteresis', key: 'hysteresis' },
        { title: 'Resonant Frequency', dataIndex: 'resonant_frequency', key: 'resonant_frequency' },
        { title: 'Repeatability', dataIndex: 'repeatability', key: 'repeatability' },
        { title: 'Accuracy', dataIndex: 'accuracy', key: 'accuracy' },
        { title: 'Rise Time', dataIndex: 'rise_time', key: 'rise_time' },
        { title: 'Sensitivity', dataIndex: 'sensitivity', key: 'sensitivity' },
        { title: 'Calibration Equation', dataIndex: 'calibration_equation', key: 'calibration_equation' },
        { title: 'Calibrator', dataIndex: 'calibrator', key: 'calibrator' },
        { title: 'Reviewer', dataIndex: 'reviewer', key: 'reviewer' },
        { title: 'Notes', dataIndex: 'notes', key: 'notes' },
        {
            title: 'Action',
            key: 'action',
            render: (_, record) => (
                <Space size="middle">
                    <Button onClick={() => handleEdit(record)}>Edit</Button>
                    <Popconfirm
                        title="Are you sure to delete this calibration?"
                        onConfirm={() => handleDelete(record.id)}
                        okText="Yes"
                        cancelText="No"
                    >
                        <Button danger>Delete</Button>
                    </Popconfirm>
                </Space>
            ),
        },
    ];

    return (
        <div>
            <h1>Sensor Calibration Management for Sensor ID: {sensorId}</h1>
            <Button type="primary" onClick={handleAdd} style={{ marginBottom: 16 }}>
                Add New Calibration
            </Button>
            <Table columns={columns} dataSource={calibrations} rowKey="id" loading={loading} />

            <Modal
                title={editingCalibration ? 'Edit Calibration' : 'Add New Calibration'}
                open={isModalVisible}
                onOk={handleModalOk}
                onCancel={handleModalCancel}
            >
                <Form form={form} layout="vertical">
                    <Form.Item name="calibration_instrument" label="Calibration Instrument" rules={[{ required: true, message: 'Please input the calibration instrument!' }]}>
                        <Input />
                    </Form.Item>
                    <Form.Item name="calibration_range" label="Calibration Range">
                        <Input />
                    </Form.Item>
                    <Form.Item name="calibration_date" label="Calibration Date">
                        <Input type="date" />
                    </Form.Item>
                    <Form.Item name="pressure_values" label="Pressure Values">
                        <Input.TextArea rows={4} placeholder='Enter as JSON string: [{"value": 0, "unit": "psi"}]' />
                    </Form.Item>
                    <Form.Item name="voltage_values" label="Voltage Values">
                        <Input.TextArea rows={4} placeholder='Enter as JSON string: [{"value": 0, "unit": "V"}]' />
                    </Form.Item>
                    <Form.Item name="non_linearity" label="Non-linearity">
                        <Input type="number" step="0.01" />
                    </Form.Item>
                    <Form.Item name="hysteresis" label="Hysteresis">
                        <Input type="number" step="0.01" />
                    </Form.Item>
                    <Form.Item name="resonant_frequency" label="Resonant Frequency">
                        <Input type="number" step="0.01" />
                    </Form.Item>
                    <Form.Item name="repeatability" label="Repeatability">
                        <Input type="number" step="0.01" />
                    </Form.Item>
                    <Form.Item name="accuracy" label="Accuracy">
                        <Input type="number" step="0.01" />
                    </Form.Item>
                    <Form.Item name="rise_time" label="Rise Time">
                        <Input type="number" step="0.01" />
                    </Form.Item>
                    <Form.Item name="sensitivity" label="Sensitivity">
                        <Input type="number" step="0.01" />
                    </Form.Item>
                    <Form.Item name="calibration_equation" label="Calibration Equation">
                        <Input.TextArea rows={2} />
                    </Form.Item>
                    <Form.Item name="calibrator" label="Calibrator">
                        <Input />
                    </Form.Item>
                    <Form.Item name="reviewer" label="Reviewer">
                        <Input />
                    </Form.Item>
                    <Form.Item name="notes" label="Notes">
                        <Input.TextArea rows={3} />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default SensorCalibrationManagementPage;