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
      title="试验排班详情"
      bordered 
      column={1}
      size="small"
      style={{ marginBottom: '16px' }}
    >
      <Descriptions.Item label="试验名称">
        <strong>{selectedTrial.title}</strong>
      </Descriptions.Item>
      <Descriptions.Item label="客户">{selectedTrial.client}</Descriptions.Item>
      <Descriptions.Item label="状态">
        <Badge 
          color={status.color}
          text={<>
            {status.icon} {status.text}
          </>}
          style={{ fontWeight: 'bold' }}
        />
      </Descriptions.Item>
      <Descriptions.Item label="版本">v{selectedTrial.version || '1.0'}</Descriptions.Item>
      <Descriptions.Item label="排班周期">
        {selectedTrial.start_date} 至 {selectedTrial.end_date}
      </Descriptions.Item>
      <Descriptions.Item label="排班统计">
        {selectedTrial.time_slots?.length || 0} 个时间段
      </Descriptions.Item>
      <Descriptions.Item label="负责人">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {selectedTrial.responsible_persons?.map(person => (
            <Tag key={person.id} color="blue" style={{ margin: 0 }}>
              {person.name} ({person.role || '成员'})
            </Tag>
          ))}
        </div>
      </Descriptions.Item>
      <Descriptions.Item label="设备">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {selectedTrial.equipment?.map(item => (
            <Tag key={item.id} color="green" style={{ margin: 0 }}>
              {item.name} ({item.type || '设备'})
            </Tag>
          ))}
        </div>
      </Descriptions.Item>
      <Descriptions.Item label="试验描述">
        <div style={{ whiteSpace: 'pre-wrap' }}>
          {selectedTrial.description || '暂无详细描述'}
        </div>
      </Descriptions.Item>
    </Descriptions>
  );
};

export default TrialDetails;
