import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Table, Button, Modal, message, Spin, Card, Descriptions, Tag, Divider } from 'antd';
import { getCalibrationRecords, deleteCalibrationRecord } from '../api/sensorApi';
import dayjs from 'dayjs';
import { logger } from '../../../shared/utils/logger';

const SensorCalibrationHistoryPage = () => {
  const { sensorId } = useParams();
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);

  const fetchRecords = useCallback(async () => {
    try {
      setLoading(true);
      const response = await getCalibrationRecords({ sensor: sensorId });
      setRecords(response.data);
    } catch (error) {
      message.error('获取校准记录失败');
      logger.error('Failed to fetch calibration records:', error);
    } finally {
      setLoading(false);
    }
  }, [sensorId]);

  useEffect(() => {
    if (sensorId) {
      fetchRecords();
    }
  }, [sensorId, fetchRecords]);

  const handleDelete = (id) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这条校准记录吗？',
      okText: '确认',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteCalibrationRecord(id);
          message.success('校准记录删除成功');
          fetchRecords();
        } catch (error) {
          message.error('删除失败');
          logger.error('Failed to delete calibration record:', error);
        }
      },
    });
  };

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
      render: (text) => dayjs(text).format('YYYY-MM-DD'),
    },
    {
      title: '校准仪器',
      dataIndex: 'calibration_instrument',
      key: 'calibration_instrument',
    },
    {
      title: '校准人',
      dataIndex: 'calibrated_by_username',
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
        <div>
          <Button type="link" onClick={() => showModal(record)}>
            查看详情
          </Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>
            删除
          </Button>
        </div>
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
          width={900}
          footer={[
            <Button key="back" onClick={handleCancel}>
              关闭
            </Button>,
          ]}
        >
          <Descriptions title="基本信息" bordered column={2} size="small">
            <Descriptions.Item label="校准日期">{dayjs(selectedRecord.calibration_date).format('YYYY-MM-DD')}</Descriptions.Item>
            <Descriptions.Item label="校准仪器">{selectedRecord.calibration_instrument || '无'}</Descriptions.Item>
            <Descriptions.Item label="校准人">{selectedRecord.calibrated_by_username || selectedRecord.calibrated_by || '无'}</Descriptions.Item>
            <Descriptions.Item label="审核人">{selectedRecord.reviewed_by_username || selectedRecord.reviewed_by || '无'}</Descriptions.Item>
            <Descriptions.Item label="室温">{selectedRecord.room_temperature ? `${selectedRecord.room_temperature}°C` : '—'}</Descriptions.Item>
            <Descriptions.Item label="相对湿度">{selectedRecord.relative_humidity ? `${selectedRecord.relative_humidity}%` : '—'}</Descriptions.Item>
          </Descriptions>

          <Divider orientation="left" style={{ margin: '16px 0 12px' }}>性能指标</Divider>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
            <Tag color="blue" style={{ padding: '4px 12px', fontSize: 14 }}>非线性度: {selectedRecord.non_linearity ?? '—'}%</Tag>
            <Tag color="green" style={{ padding: '4px 12px', fontSize: 14 }}>迟滞: {selectedRecord.hysteresis ?? '—'}%</Tag>
            <Tag color="orange" style={{ padding: '4px 12px', fontSize: 14 }}>重复性: {selectedRecord.repeatability ?? '—'}%</Tag>
            <Tag color="purple" style={{ padding: '4px 12px', fontSize: 14 }}>准确度: {selectedRecord.accuracy ?? '—'}%</Tag>
            <Tag color="cyan" style={{ padding: '4px 12px', fontSize: 14 }}>灵敏度: {selectedRecord.sensitivity ?? '—'} mV/V</Tag>
          </div>

          <Descriptions bordered column={1} size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label="校准方程">{selectedRecord.calibration_equation || '无'}</Descriptions.Item>
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
        </Modal>
      )}
    </Spin>
  );
};

export default SensorCalibrationHistoryPage;