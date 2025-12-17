import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Table, Button, Modal, message, Spin, Card } from 'antd';
import { getCalibrationRecords } from '../api/sensorApi';
import moment from 'moment';

const SensorCalibrationHistoryPage = () => {
  const { sensorId } = useParams();
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        setLoading(true);
        const response = await getCalibrationRecords({ sensor: sensorId });
        setRecords(response.data);
      } catch (error) {
        message.error('获取校准记录失败');
        console.error('Failed to fetch calibration records:', error);
      } finally {
        setLoading(false);
      }
    };

    if (sensorId) {
      fetchRecords();
    }
  }, [sensorId]);

  const showModal = (record) => {
    setSelectedRecord(record);
    setIsModalVisible(true);
  };

  const handleOk = () => {
    setIsModalVisible(false);
    setSelectedRecord(null);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setSelectedRecord(null);
  };

  const columns = [
    {
      title: '校准日期',
      dataIndex: 'calibration_date',
      key: 'calibration_date',
      render: (text) => moment(text).format('YYYY-MM-DD'),
    },
    {
      title: '校准仪器',
      dataIndex: 'calibration_instrument',
      key: 'calibration_instrument',
    },
    {
      title: '校准人',
      dataIndex: 'calibrated_by',
      key: 'calibrated_by',
    },
    {
      title: '审核人',
      dataIndex: 'reviewed_by',
      key: 'reviewed_by',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Button type="link" onClick={() => showModal(record)}>
          查看详情
        </Button>
      ),
    },
  ];

  return (
    <Spin spinning={loading}>
      <Card title={`传感器 #${sensorId} 的校准历史`}>
        <Table
          columns={columns}
          dataSource={records}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>
      {selectedRecord && (
        <Modal
          title="校准记录详情"
          open={isModalVisible}
          onOk={handleOk}
          onCancel={handleCancel}
          width={800}
          footer={[
            <Button key="back" onClick={handleCancel}>
              关闭
            </Button>,
          ]}
        >
          <p><strong>校准日期:</strong> {moment(selectedRecord.calibration_date).format('YYYY-MM-DD')}</p>
          <p><strong>校准仪器:</strong> {selectedRecord.calibration_instrument}</p>
          <p><strong>室温:</strong> {selectedRecord.room_temperature}°C</p>
          <p><strong>相对湿度:</strong> {selectedRecord.relative_humidity}%</p>
          <p><strong>非线性度:</strong> {selectedRecord.non_linearity}%</p>
          <p><strong>迟滞:</strong> {selectedRecord.hysteresis}%</p>
          <p><strong>重复性:</strong> {selectedRecord.repeatability}%</p>
          <p><strong>准确度:</strong> {selectedRecord.accuracy}%</p>
          <p><strong>灵敏度:</strong> {selectedRecord.sensitivity} mV/V</p>
          <p><strong>校准方程:</strong> {selectedRecord.calibration_equation}</p>
          <p><strong>校准人:</strong> {selectedRecord.calibrated_by}</p>
          <p><strong>审核人:</strong> {selectedRecord.reviewed_by}</p>
          <Card title="数据点" size="small" style={{ marginTop: 16 }}>
            <Table
              bordered
              dataSource={selectedRecord.data_points}
              columns={[
                { title: '压力', dataIndex: 'pressure', key: 'pressure' },
                { title: '正行程1 (mV)', dataIndex: 'positive_trip_voltage_1', key: 'positive_trip_voltage_1' },
                { title: '负行程1 (mV)', dataIndex: 'negative_trip_voltage_1', key: 'negative_trip_voltage_1' },
                { title: '正行程2 (mV)', dataIndex: 'positive_trip_voltage_2', key: 'positive_trip_voltage_2' },
                { title: '负行程2 (mV)', dataIndex: 'negative_trip_voltage_2', key: 'negative_trip_voltage_2' },
                { title: '正行程3 (mV)', dataIndex: 'positive_trip_voltage_3', key: 'positive_trip_voltage_3' },
                { title: '负行程3 (mV)', dataIndex: 'negative_trip_voltage_3', key: 'negative_trip_voltage_3' },
              ]}
              pagination={false}
              rowKey="id"
            />
          </Card>
        </Modal>
      )}
    </Spin>
  );
};

export default SensorCalibrationHistoryPage;