/**
 * 多 Agent 任务面板 (/smart-assistant/tasks)
 *
 * 功能:
 * - 提交任务目标 → Supervisor 分解 → 创建并执行
 * - 任务列表(状态标签) + 选中任务的实时时间线(SSE 增量追加)
 * - 人工介入: 暂停 / 恢复 / 终止(后端 intervene 端点当前仅支持这三个动作)
 * - 组件卸载 / 切换任务时通过 AbortController 断开 SSE
 *
 * 拆分:业务逻辑在 hooks/useAgentTaskPanel.js,UI 区块在 components/agentTask/。
 */
import { Col, Row, Typography } from 'antd';
import TaskCreateForm from '../components/agentTask/TaskCreateForm';
import TaskListPanel from '../components/agentTask/TaskListPanel';
import TaskDetailPanel from '../components/agentTask/TaskDetailPanel';
import useAgentTaskPanel from '../hooks/useAgentTaskPanel';

const AgentTaskPanel = () => {
  const {
    tasks, tasksLoading, tasksError,
    goal, setGoal, createLoading, createError,
    selectedTaskId, taskDetail, subtasks, events,
    detailLoading, detailError, streaming, streamError,
    interveneLoading,
    loadTasks, handleSelectTask, handleCreateAndExecute, handleIntervene,
  } = useAgentTaskPanel();

  return (
    <div style={{ padding: 24 }}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        多 Agent 任务
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        提交复杂目标，由 Supervisor 拆解为多个子任务协作执行；支持实时进度查看与人工介入。
      </Typography.Paragraph>

      <TaskCreateForm
        goal={goal}
        createLoading={createLoading}
        createError={createError}
        onGoalChange={setGoal}
        onCreate={handleCreateAndExecute}
      />

      <Row gutter={16}>
        {/* 任务列表 */}
        <Col xs={24} md={9} lg={8}>
          <TaskListPanel
            tasks={tasks}
            tasksLoading={tasksLoading}
            tasksError={tasksError}
            selectedTaskId={selectedTaskId}
            onSelect={handleSelectTask}
            onRefresh={loadTasks}
          />
        </Col>

        {/* 任务详情 */}
        <Col xs={24} md={15} lg={16}>
          <TaskDetailPanel
            selectedTaskId={selectedTaskId}
            taskDetail={taskDetail}
            subtasks={subtasks}
            events={events}
            detailLoading={detailLoading}
            detailError={detailError}
            streaming={streaming}
            streamError={streamError}
            interveneLoading={interveneLoading}
            onIntervene={handleIntervene}
          />
        </Col>
      </Row>
    </div>
  );
};

export default AgentTaskPanel;
