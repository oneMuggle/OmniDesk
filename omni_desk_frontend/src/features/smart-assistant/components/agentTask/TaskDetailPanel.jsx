import { Alert, Card, Empty, List, Space, Spin, Tag, Typography } from 'antd';
import PropTypes from 'prop-types';
import { SUBTASK_STATUS_MAP, TASK_STATUS_MAP } from '../../api/agentTaskApi';
import { statusInfoOf } from '../../utils/agentTaskUtils';
import AgentLogStream from './AgentLogStream';
import TaskInterveneActions from './TaskInterveneActions';

const TaskDetailPanel = ({
  selectedTaskId,
  taskDetail,
  subtasks,
  events,
  detailLoading,
  detailError,
  streaming,
  streamError,
  interveneLoading,
  onIntervene,
}) => {
  const detailStatusInfo = taskDetail ? statusInfoOf(taskDetail.status, TASK_STATUS_MAP) : null;

  return (
    <Card size="small" title="任务详情">
      {!selectedTaskId && <Empty description="请从左侧选择一个任务" />}

      {selectedTaskId && detailLoading && !taskDetail && (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
        </div>
      )}

      {selectedTaskId && detailError && (
        <Alert type="error" showIcon message={detailError} />
      )}

      {selectedTaskId && taskDetail && (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          {/* 概要 */}
          <Space size={8} wrap>
            <Typography.Text strong>{taskDetail.objective}</Typography.Text>
            <Tag color={detailStatusInfo.color}>{detailStatusInfo.label}</Tag>
            {streaming && <Tag color="processing">实时进度接收中</Tag>}
          </Space>

          {/* 人工介入 */}
          <TaskInterveneActions
            status={taskDetail.status}
            interveneLoading={interveneLoading}
            onIntervene={onIntervene}
          />

          {streamError && <Alert type="warning" showIcon message={streamError} />}

          {/* 子任务 */}
          {subtasks.length > 0 && (
            <List
              size="small"
              header={<Typography.Text strong>子任务</Typography.Text>}
              dataSource={subtasks}
              renderItem={(sub) => {
                const info = statusInfoOf(sub.status, SUBTASK_STATUS_MAP);
                return (
                  <List.Item>
                    <Space size={8} wrap>
                      <Tag>{sub.role}</Tag>
                      <span>{sub.objective}</span>
                      <Tag color={info.color}>{info.label}</Tag>
                    </Space>
                  </List.Item>
                );
              }}
            />
          )}

          {/* 执行时间线 */}
          <AgentLogStream events={events} detailLoading={detailLoading} />

          {/* 最终产出 */}
          {taskDetail.final_output && (
            <div>
              <Typography.Text strong>最终产出</Typography.Text>
              <pre
                style={{
                  maxHeight: 240,
                  overflow: 'auto',
                  padding: 8,
                  marginTop: 8,
                  background: 'rgba(0, 0, 0, 0.04)',
                }}
              >
                {JSON.stringify(taskDetail.final_output, null, 2)}
              </pre>
            </div>
          )}
        </Space>
      )}
    </Card>
  );
};

TaskDetailPanel.propTypes = {
  selectedTaskId: PropTypes.string,
  taskDetail: PropTypes.shape({
    task_id: PropTypes.string,
    objective: PropTypes.string,
    status: PropTypes.string,
    final_output: PropTypes.any,
  }),
  subtasks: PropTypes.array,
  events: PropTypes.array,
  detailLoading: PropTypes.bool,
  detailError: PropTypes.string,
  streaming: PropTypes.bool,
  streamError: PropTypes.string,
  interveneLoading: PropTypes.bool,
  onIntervene: PropTypes.func.isRequired,
};

export default TaskDetailPanel;
