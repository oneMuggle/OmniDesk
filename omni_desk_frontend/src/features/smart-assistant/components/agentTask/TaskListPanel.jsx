import { Alert, Button, Card, Empty, List } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
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

TaskListPanel.propTypes = {
  tasks: PropTypes.array,
  tasksLoading: PropTypes.bool,
  tasksError: PropTypes.string,
  selectedTaskId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
  onRefresh: PropTypes.func.isRequired,
};

export default TaskListPanel;
