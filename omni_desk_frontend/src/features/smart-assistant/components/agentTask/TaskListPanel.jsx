import { Alert, Button, Card, Empty, List } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import AgentTaskItem from './AgentTaskItem';

const TaskListPanel = ({ tasks, tasksLoading, tasksError, selectedTaskId, onSelect, onRefresh }) => (
  <Card
    size="small"
    title="任务列表"
    extra={
      <Button size="small" icon={<ReloadOutlined />} loading={tasksLoading} onClick={onRefresh}>
        刷新
      </Button>
    }
  >
    {tasksError ? (
      <Alert type="error" showIcon message={tasksError} />
    ) : (
      <List
        size="small"
        loading={tasksLoading}
        dataSource={tasks}
        locale={{ emptyText: <Empty description="暂无任务" /> }}
        renderItem={(task) => (
          <AgentTaskItem
            task={task}
            selected={task.task_id === selectedTaskId}
            onClick={() => onSelect(task.task_id)}
          />
        )}
      />
    )}
  </Card>
);

export default TaskListPanel;
