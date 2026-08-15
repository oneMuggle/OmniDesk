import { List, Space, Tag } from 'antd';
import { TASK_STATUS_MAP } from '../../api/agentTaskApi';
import { formatTime, statusInfoOf } from '../../utils/agentTaskUtils';

const AgentTaskItem = ({ task, selected, onClick }) => {
  const info = statusInfoOf(task.status, TASK_STATUS_MAP);
  return (
    <List.Item
      onClick={onClick}
      style={{
        cursor: 'pointer',
        background: selected ? 'rgba(22, 119, 255, 0.08)' : undefined,
      }}
    >
      <List.Item.Meta
        title={
          <Space size={8} wrap>
            <span>{task.objective}</span>
            <Tag color={info.color}>{info.label}</Tag>
          </Space>
        }
        description={`创建于 ${formatTime(task.created_at)}`}
      />
    </List.Item>
  );
};

export default AgentTaskItem;
