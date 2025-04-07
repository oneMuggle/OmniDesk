import React from 'react';
import { Descriptions, Badge, Tag } from 'antd';

const TrialDetails = ({ selectedTrial }) => {
  if (!selectedTrial) return null;

  const statusConfig = {
    planned: {
      color: '#1890ff',
      text: '已计划',
      icon: '🗓️',
      badgeStyle: { backgroundColor: '#1890ff' }
    },
    in_progress: {
      color: '#52c41a',
      text: '进行中',
      icon: '🔄',
      badgeStyle: { backgroundColor: '#52c41a' }
    },
    completed: {
      color: '#888',
      text: '已完成',
      icon: '✅',
      badgeStyle: { backgroundColor: '#888' }
    },
    cancelled: {
      color: '#ff4d4f',
      text: '已取消',
      icon: '❌',
      badgeStyle: { backgroundColor: '#ff4d4f' }
    }
  };

  const getStatusConfig = (status) => 
    statusConfig[status] || {
      color: '#d3d3d3',
      text: '未知状态',
      icon: '❓',
      badgeStyle: { backgroundColor: '#d3d3d3' }
    };

  const status = getStatusConfig(selectedTrial.status);

  return (
    <Descriptions 
      title="试验详情" 
      bordered 
      column={1}
      size="small"
      style={{ marginBottom: '16px' }}
    >
      <Descriptions.Item label="试验名称">{selectedTrial.title}</Descriptions.Item>
      <Descriptions.Item label="客户">{selectedTrial.client}</Descriptions.Item>
      <Descriptions.Item label="状态">
        <Badge 
          color={status.color} 
          text={status.text}
        />
      </Descriptions.Item>
      <Descriptions.Item label="开始日期">{selectedTrial.start_date}</Descriptions.Item>
      <Descriptions.Item label="结束日期">{selectedTrial.end_date}</Descriptions.Item>
      <Descriptions.Item label="负责人">
        {selectedTrial.responsible_persons?.map(person => (
          <Tag key={person.id} color="blue">
            {person.name}
          </Tag>
        ))}
      </Descriptions.Item>
      <Descriptions.Item label="设备">
        {selectedTrial.equipment?.map(item => (
          <Tag key={item.id} color="green">
            {item.name}
          </Tag>
        ))}
      </Descriptions.Item>
      <Descriptions.Item label="描述">
        {selectedTrial.description || '无描述'}
      </Descriptions.Item>
    </Descriptions>
  );
};

export default TrialDetails;
