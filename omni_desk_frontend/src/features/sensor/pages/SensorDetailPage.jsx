import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Table, Button, Card, Spin, Alert, Modal, message, Descriptions, Tag, Divider } from 'antd';
import apiClient from '../../../shared/api/apiClient';
import SensorCalibrationForm from '../components/SensorCalibrationForm';
import { logger } from '../../../shared/utils/logger';

const SensorDetailPage = () => {
    const { sensorId } = useParams();
    const [sensor, setSensor] = useState(null);
    const [calibrations, setCalibrations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [selectedRecord, setSelectedRecord] = useState(null);

    const fetchSensorDetails = useCallback(async () => {
        try {
            setLoading(true);
            const sensorRes = await apiClient.get(`/sensor-management/sensors/${sensorId}/`);
            const calibrationsRes = await apiClient.get(`/sensor-management/sensor-calibrations/?sensor=${sensorId}`);
            setSensor(sensorRes.data);
            setCalibrations(calibrationsRes.data?.results ?? calibrationsRes.data ?? []);
            setError(null);
        } catch (err) {
            setError('无法加载传感器详情。');
            logger.error(err);
        } finally {
            setLoading(false);
        }
    }, [sensorId]);

    useEffect(() => {
        fetchSensorDetails();
    }, [fetchSensorDetails]);

    const handleAddCalibration = () => {
        setSelectedRecord(null);
        setIsModalVisible(true);
    };

    const handleModalCancel = () => {
        setIsModalVisible(false);
    };

    const handleFormSubmit = async (values) => {
        try {
            await apiClient.post(`/sensor-management/sensor-calibrations/`, { ...values, sensor: sensorId });
            setIsModalVisible(false);
            fetchSensorDetails(); // Refresh details
        } catch (error) {
            logger.error('Failed to add calibration record', error);
        }
    };

    const showModal = (record) => {
        setSelectedRecord(record);
        setIsModalVisible(true);
    };

    const handleDeleteCalibration = (id) => {
        Modal.confirm({
            title: '确认删除',
            content: '确定要删除这条校准记录吗？',
            okText: '确认',
            cancelText: '取消',
            okType: 'danger',
            onOk: async () => {
                try {
                    await apiClient.delete(`/sensor-management/sensor-calibrations/${id}/`);
                    message.success('校准记录删除成功');
                    fetchSensorDetails();
                } catch (error) {
                    message.error('删除失败');
                    logger.error('Failed to delete calibration record:', error);
                }
            },
        });
    };

    const columns = [
        { title: '校准日期', dataIndex: 'calibration_date', key: 'calibration_date' },
        { title: '校准人', dataIndex: 'calibrated_by_username', key: 'calibrated_by' },
        { title: '精度', dataIndex: 'accuracy', key: 'accuracy' },
        {
            title: '操作',
            key: 'action',
            render: (_, record) => (
                <div>
                    <Button size="small" onClick={() => showModal(record)} style={{ marginRight: 4 }}>查看详情</Button>
                    <Button size="small" danger onClick={() => handleDeleteCalibration(record.id)}>删除</Button>
                </div>
            ),
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
                <p><strong>状态:</strong> {sensor?.status_display}</p>
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
                open={isModalVisible && !selectedRecord}
                onCancel={handleModalCancel}
                footer={null}
            >
                <SensorCalibrationForm
                    onSubmit={handleFormSubmit}
                />
            </Modal>
            <Modal
                title="校准记录详情"
                open={isModalVisible && !!selectedRecord}
                onCancel={handleModalCancel}
                footer={<Button onClick={handleModalCancel}>关闭</Button>}
                width={900}
            >
                {selectedRecord && (
                    <div>
                        <Descriptions title="基本信息" bordered column={2} size="small">
                            <Descriptions.Item label="校准日期">{selectedRecord.calibration_date}</Descriptions.Item>
                            <Descriptions.Item label="校准仪器">{selectedRecord.calibration_instrument || '无'}</Descriptions.Item>
                            <Descriptions.Item label="校准范围">{selectedRecord.calibration_range || '无'}</Descriptions.Item>
                            <Descriptions.Item label="校准人">{selectedRecord.calibrated_by_username || selectedRecord.calibrated_by || '无'}</Descriptions.Item>
                        </Descriptions>

                        <Divider orientation="left" style={{ margin: '16px 0 12px' }}>性能指标</Divider>
                        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
                            <Tag color="blue" style={{ padding: '4px 12px', fontSize: 14 }}>非线性度: {selectedRecord.non_linearity ?? '—'}%</Tag>
                            <Tag color="green" style={{ padding: '4px 12px', fontSize: 14 }}>迟滞: {selectedRecord.hysteresis ?? '—'}%</Tag>
                            <Tag color="orange" style={{ padding: '4px 12px', fontSize: 14 }}>重复性: {selectedRecord.repeatability ?? '—'}%</Tag>
                            <Tag color="purple" style={{ padding: '4px 12px', fontSize: 14 }}>精度: {selectedRecord.accuracy ?? '—'}%</Tag>
                            <Tag color="cyan" style={{ padding: '4px 12px', fontSize: 14 }}>灵敏度: {selectedRecord.sensitivity ?? '—'} mV/V</Tag>
                        </div>

                        <Descriptions bordered column={1} size="small" style={{ marginBottom: 16 }}>
                            <Descriptions.Item label="校准方程">{selectedRecord.calibration_equation || '无'}</Descriptions.Item>
                            <Descriptions.Item label="备注">{selectedRecord.remarks || '无'}</Descriptions.Item>
                        </Descriptions>

                        {selectedRecord.data_points && selectedRecord.data_points.length > 0 && (
                            <>
                                <Divider orientation="left" style={{ margin: '16px 0 12px' }}>数据点</Divider>
                                <Table
                                    bordered
                                    dataSource={selectedRecord.data_points}
                                    columns={[
                                        { title: '压力值', dataIndex: 'pressure_value', key: 'pressure_value', align: 'center' },
                                        { title: '正行程1 (mV)', dataIndex: 'positive_trip_voltage_1', key: 'positive_trip_voltage_1', align: 'center' },
                                        { title: '负行程1 (mV)', dataIndex: 'negative_trip_voltage_1', key: 'negative_trip_voltage_1', align: 'center' },
                                        { title: '正行程2 (mV)', dataIndex: 'positive_trip_voltage_2', key: 'positive_trip_voltage_2', align: 'center' },
                                        { title: '负行程2 (mV)', dataIndex: 'negative_trip_voltage_2', key: 'negative_trip_voltage_2', align: 'center' },
                                        { title: '正行程3 (mV)', dataIndex: 'positive_trip_voltage_3', key: 'positive_trip_voltage_3', align: 'center' },
                                        { title: '负行程3 (mV)', dataIndex: 'negative_trip_voltage_3', key: 'negative_trip_voltage_3', align: 'center' },
                                    ]}
                                    pagination={false}
                                    rowKey="id"
                                    size="small"
                                    scroll={{ x: true }}
                                />
                            </>
                        )}
                    </div>
                )}
            </Modal>
        </div>
    );
};

export default SensorDetailPage;