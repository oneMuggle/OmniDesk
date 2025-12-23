import React, { useState, useEffect } from 'react';
import { Card, Table, message, Space, Tag } from 'antd';
import moment from 'moment';
import apiClient from '../api/apiClient';

const SensorMovementHistoryPage = () => {
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchMovements();
  }, []);

  const fetchMovements = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/api/sensor-management/sensor-movements/');
      setMovements(Array.isArray(response.data.results) ? response.data.results : []);
    } catch (error) {
      message.error('获取传感器出入库记录失败!');
      console.error('Error fetching sensor movements:', error);
    } finally {
      setLoading(false);
    }
  };

  const getMovementTypeTag = (type) => {
    switch (type) {
      case 'in':
        return <Tag color="green">入库</Tag>;
      case 'out':
        return <Tag color="red">出库</Tag>;
      default:
        return <Tag>{type}</Tag>;
    }
  };

  const columns = [
    {
      title: '传感器序列号',
      dataIndex: 'sensor_serial_number',
      key: 'sensor_serial_number',
    },
    {
      title: '操作类型',
      dataIndex: 'movement_type',
      key: 'movement_type',
      render: (type) => getMovementTypeTag(type),
      filters: [
        { text: '入库', value: 'in' },
        { text: '出库', value: 'out' },
      ],
      onFilter: (value, record) => record.movement_type === value,
    },
    {
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      sorter: (a, b) => a.quantity - b.quantity,
    },
    {
      title: '操作人员',
      dataIndex: 'operator_username',
      key: 'operator_username',
    },
    {
      title: '出入库日期',
      dataIndex: 'movement_date',
      key: 'movement_date',
      render: (text) => text ? moment(text).format('YYYY-MM-DD HH:mm:ss') : 'N/A',
      sorter: (a, b) => moment(a.movement_date).unix() - moment(b.movement_date).unix(),
    },
    {
      title: '去向/来源',
      dataIndex: 'destination_source',
      key: 'destination_source',
    },
    {
      title: '备注',
      dataIndex: 'reason',
      key: 'reason',
    },
  ];

  return (
    <Card title="传感器出入库历史记录">
      <Table
        columns={columns}
        dataSource={movements}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />
    </Card>
  );
};

export default SensorMovementHistoryPage;