import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Table, Button, Card, Spin, Alert, Modal } from 'antd';
import apiClient from '../api/apiClient';
import SensorCalibrationForm from '../components/sensor/SensorCalibrationForm';

const SensorDetailPage = () => {
    const { id } = useParams();
    const [sensor, setSensor] = useState(null);
    const [calibrations, setCalibrations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isModalVisible, setIsModalVisible] = useState(false);

    const fetchSensorDetails = useCallback(async () => {
        try {
            setLoading(true);
            const sensorRes = await apiClient.get(`/sensors/${id}/`);
            const calibrationsRes = await apiClient.get(`/sensors/${id}/calibrations/`);
            setSensor(sensorRes);
            setCalibrations(calibrationsRes);
            setError(null);
        } catch (err) {
            setError('无法加载传感器详情。');
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => {
        fetchSensorDetails();
    }, [fetchSensorDetails]);

    const handleAddCalibration = () => {
        setIsModalVisible(true);
    };

    const handleModalCancel = () => {
        setIsModalVisible(false);
    };

    const handleFormSubmit = async (values) => {
        try {
            await apiClient.post(`/sensors/${id}/calibrations/`, values);
            setIsModalVisible(false);
            fetchSensorDetails(); // Refresh details
        } catch (error) {
            console.error('Failed to add calibration record', error);
        }
    };

    const columns = [
        { title: '校准日期', dataIndex: 'calibration_date', key: 'calibration_date' },
        { title: '校准人', dataIndex: 'calibrated_by_username', key: 'calibrated_by' },
        { title: '精度', dataIndex: 'accuracy', key: 'accuracy' },
        {
            title: '操作',
            key: 'action',
            render: () => <Button size="small">查看详情</Button>,
        },
    ];

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}>
                <Spin tip="加载中..." />
            </div>
        );
    }

    if (error) {
        return <Alert message="错误" description={error} type="error" showIcon />;
    }

    return (
        <div style={{ padding: '20px' }}>
            <Card title={`传感器详情: ${sensor?.name}`}>
                <p><strong>传感器编号:</strong> {sensor?.sensor_number}</p>
                <p><strong>序列号:</strong> {sensor?.serial_number}</p>
                <p><strong>状态:</strong> {sensor?.status}</p>
            </Card>

            <Card title="校准记录" style={{ marginTop: '20px' }} extra={<Button type="primary" onClick={handleAddCalibration}>添加校准记录</Button>}>
                <Table
                    dataSource={calibrations}
                    columns={columns}
                    rowKey="id"
                    pagination={false}
                />
            </Card>
            <Modal
                title="添加校准记录"
                open={isModalVisible}
                onCancel={handleModalCancel}
                footer={null}
            >
                <SensorCalibrationForm
                    onSubmit={handleFormSubmit}
                />
            </Modal>
        </div>
    );
};

export default SensorDetailPage;