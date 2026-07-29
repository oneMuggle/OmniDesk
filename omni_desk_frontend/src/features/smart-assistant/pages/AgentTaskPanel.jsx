/**
 * 多 Agent 任务面板 (/smart-assistant/tasks)
 *
 * 功能:
 * - 提交任务目标 → Supervisor 分解 → 创建并执行
 * - 任务列表(状态标签) + 选中任务的实时时间线(SSE 增量追加)
 * - 人工介入: 暂停 / 恢复 / 终止(后端 intervene 端点当前仅支持这三个动作)
 * - 组件卸载 / 切换任务时通过 AbortController 断开 SSE
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  List,
  Popconfirm,
  Row,
  Space,
  Spin,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd';
import {
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons';
import {
  EVENT_TYPE_LABELS,
  SUBTASK_STATUS_MAP,
  TASK_STATUS_MAP,
  createAgentTask,
  executeAgentTask,
  getAgentTasks,
  getAgentTaskTimeline,
  interveneAgentTask,
  subscribeTaskStream,
} from '../api/agentTaskApi';

const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled'];

/** 事件类型 → 时间线节点颜色 */
const eventColor = (type) => {
  if (type.endsWith('.failed')) return 'red';
  if (type.endsWith('.completed')) return 'green';
  if (type.startsWith('task.')) return 'blue';
  if (type.startsWith('supervisor.') || type.startsWith('user.')) return 'purple';
  if (type === 'hook.triggered') return 'orange';
  return 'gray';
};

const formatTime = (iso) => (iso ? String(iso).replace('T', ' ').slice(0, 19) : '');

const formatPayload = (payload) => {
  if (!payload || typeof payload !== 'object' || Object.keys(payload).length === 0) {
    return null;
  }
  const text = JSON.stringify(payload);
  return text.length > 140 ? `${text.slice(0, 140)}…` : text;
};

/** 历史事件(AgentEventSerializer: sequence/event_type/subtask/payload/created_at) → 统一结构 */
const normalizeHistoryEvent = (event) => ({
  key: `h-${event.sequence}`,
  sequence: event.sequence,
  type: event.event_type,
  subtaskRef: event.subtask ? `#${event.subtask}` : null,
  payload: event.payload,
  time: event.created_at,
});

/** SSE 事件({type, sequence, subtask_id, payload, timestamp}) → 统一结构 */
const normalizeStreamEvent = (event) => ({
  key: `s-${event.sequence}`,
  sequence: event.sequence,
  type: event.type,
  subtaskRef: event.subtask_id || null,
  payload: event.payload,
  time: event.timestamp,
});

const statusInfoOf = (status, map) => map[status] || { label: status, color: 'default' };

const AgentTaskPanel = () => {
  // 任务列表
  const [tasks, setTasks] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [tasksError, setTasksError] = useState(null);
  // 创建表单
  const [goal, setGoal] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState(null);
  // 选中任务详情
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [taskDetail, setTaskDetail] = useState(null);
  const [subtasks, setSubtasks] = useState([]);
  const [events, setEvents] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  // SSE 状态
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState(null);
  // 介入操作
  const [interveneLoading, setInterveneLoading] = useState(false);

  const subscriptionRef = useRef(null);
  const loadTaskDetailRef = useRef(null);

  const stopStream = useCallback(() => {
    if (subscriptionRef.current) {
      subscriptionRef.current.abort();
      subscriptionRef.current = null;
    }
    setStreaming(false);
  }, []);

  const loadTasks = useCallback(async () => {
    setTasksLoading(true);
    setTasksError(null);
    try {
      const response = await getAgentTasks();
      setTasks(Array.isArray(response.data) ? response.data : []);
    } catch {
      setTasksError('任务列表加载失败，请稍后重试');
    } finally {
      setTasksLoading(false);
    }
  }, []);

  /** 订阅 SSE;onDone/重连后刷新详情与列表 */
  const startStream = useCallback(
    (taskId) => {
      stopStream();
      setStreamError(null);
      setStreaming(true);
      subscriptionRef.current = subscribeTaskStream(taskId, {
        onEvent: (event) => {
          setEvents((prev) => {
            // 重连会回放全部事件,按 sequence 去重
            if (event.sequence != null && prev.some((e) => e.sequence === event.sequence)) {
              return prev;
            }
            return [...prev, normalizeStreamEvent(event)];
          });
        },
        onDone: () => {
          subscriptionRef.current = null;
          setStreaming(false);
          loadTaskDetailRef.current?.(taskId);
          loadTasks();
        },
        onTimeout: () => {
          // 服务端 60 秒轮询超时;若任务未结束则重新订阅
          subscriptionRef.current = null;
          loadTaskDetailRef.current?.(taskId, { resubscribe: true });
        },
        onError: (error) => {
          subscriptionRef.current = null;
          setStreaming(false);
          setStreamError(error.message || '实时进度连接异常');
        },
      });
    },
    [stopStream, loadTasks]
  );

  /**
   * 拉取任务时间线详情
   * @param {string} taskId 任务 ID
   * @param {{ resubscribe?: boolean }} [options] resubscribe=true 时,非终态任务自动订阅 SSE
   */
  const loadTaskDetail = useCallback(
    async (taskId, { resubscribe = false } = {}) => {
      setDetailLoading(true);
      setDetailError(null);
      try {
        const response = await getAgentTaskTimeline(taskId);
        const { task, subtasks: subs, timeline } = response.data;
        setTaskDetail(task);
        setSubtasks(subs || []);
        setEvents((timeline || []).map(normalizeHistoryEvent));

        const isTerminal = TERMINAL_STATUSES.includes(task.status);
        if (isTerminal) {
          stopStream();
        } else if (resubscribe) {
          startStream(taskId);
        }
      } catch (error) {
        setDetailError(error.response?.data?.error || '加载任务详情失败');
      } finally {
        setDetailLoading(false);
      }
    },
    [startStream, stopStream]
  );

  useEffect(() => {
    loadTaskDetailRef.current = loadTaskDetail;
  });

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // 组件卸载时断开 SSE
  useEffect(() => () => stopStream(), [stopStream]);

  const handleSelectTask = useCallback(
    (taskId) => {
      stopStream();
      setStreamError(null);
      setSelectedTaskId(taskId);
      setTaskDetail(null);
      setSubtasks([]);
      setEvents([]);
      loadTaskDetailRef.current?.(taskId, { resubscribe: true });
    },
    [stopStream]
  );

  const handleCreateAndExecute = async () => {
    const query = goal.trim();
    if (!query || createLoading) return;

    setCreateLoading(true);
    setCreateError(null);
    try {
      const created = await createAgentTask(query);
      const taskId = created.data.task_id;

      try {
        await executeAgentTask(taskId);
      } catch (execError) {
        message.warning(execError.response?.data?.error || '任务已创建，但触发执行失败');
      }

      const newTask = {
        task_id: taskId,
        objective: query,
        status: 'pending',
        created_at: new Date().toISOString(),
        subtasks: [],
      };
      setTasks((prev) => [newTask, ...prev]);
      setGoal('');
      message.success('任务创建成功，已开始执行');
      handleSelectTask(taskId);
    } catch (error) {
      setCreateError(error.response?.data?.error || '任务创建失败，请稍后重试');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleIntervene = async (action) => {
    if (!selectedTaskId || interveneLoading) return;
    setInterveneLoading(true);
    try {
      const response = await interveneAgentTask(selectedTaskId, action);
      const info = statusInfoOf(response.data.status, TASK_STATUS_MAP);
      message.success(`操作成功，当前状态：${info.label}`);
      await loadTaskDetailRef.current?.(selectedTaskId, { resubscribe: true });
      loadTasks();
    } catch (error) {
      message.error(error.response?.data?.error || '操作失败，请稍后重试');
    } finally {
      setInterveneLoading(false);
    }
  };

  const detailStatusInfo = taskDetail ? statusInfoOf(taskDetail.status, TASK_STATUS_MAP) : null;
  const canPause = taskDetail?.status === 'running';
  const canResume = taskDetail?.status === 'paused';
  const canCancel = canPause || canResume;

  return (
    <div style={{ padding: 24 }}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        多 Agent 任务
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        提交复杂目标，由 Supervisor 拆解为多个子任务协作执行；支持实时进度查看与人工介入。
      </Typography.Paragraph>

      {/* 创建表单 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="描述任务目标，如：调研 RAG 技术并整理成报告"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            onPressEnter={handleCreateAndExecute}
            disabled={createLoading}
            allowClear
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={createLoading}
            onClick={handleCreateAndExecute}
          >
            创建并执行
          </Button>
        </Space.Compact>
        {createError && (
          <Alert type="error" showIcon message={createError} style={{ marginTop: 8 }} />
        )}
      </Card>

      <Row gutter={16}>
        {/* 任务列表 */}
        <Col xs={24} md={9} lg={8}>
          <Card
            size="small"
            title="任务列表"
            extra={
              <Button size="small" icon={<ReloadOutlined />} loading={tasksLoading} onClick={loadTasks}>
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
                renderItem={(task) => {
                  const info = statusInfoOf(task.status, TASK_STATUS_MAP);
                  const selected = task.task_id === selectedTaskId;
                  return (
                    <List.Item
                      onClick={() => handleSelectTask(task.task_id)}
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
                }}
              />
            )}
          </Card>
        </Col>

        {/* 任务详情 */}
        <Col xs={24} md={15} lg={16}>
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
                <Space wrap>
                  <Button
                    size="small"
                    icon={<PauseCircleOutlined />}
                    disabled={!canPause}
                    loading={interveneLoading}
                    onClick={() => handleIntervene('pause')}
                  >
                    暂停
                  </Button>
                  <Button
                    size="small"
                    icon={<PlayCircleOutlined />}
                    disabled={!canResume}
                    loading={interveneLoading}
                    onClick={() => handleIntervene('resume')}
                  >
                    恢复
                  </Button>
                  <Popconfirm
                    title="确认终止该任务？"
                    description="终止后任务不可恢复。"
                    okText="终止"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => handleIntervene('cancel')}
                  >
                    <Button
                      size="small"
                      danger
                      icon={<StopOutlined />}
                      disabled={!canCancel}
                      loading={interveneLoading}
                    >
                      终止
                    </Button>
                  </Popconfirm>
                </Space>

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
                <div>
                  <Space size={8}>
                    <Typography.Text strong>执行时间线</Typography.Text>
                    {detailLoading && <Spin size="small" />}
                  </Space>
                  {events.length === 0 ? (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="暂无事件"
                      style={{ marginTop: 12 }}
                    />
                  ) : (
                    <Timeline
                      style={{ marginTop: 12 }}
                      items={events.map((event) => {
                        const payloadText = formatPayload(event.payload);
                        return {
                          color: eventColor(event.type),
                          children: (
                            <div key={event.key}>
                              <Space size={8} wrap>
                                <span>{EVENT_TYPE_LABELS[event.type] || event.type}</span>
                                {event.subtaskRef && <Tag>{event.subtaskRef}</Tag>}
                                {event.time && (
                                  <Typography.Text type="secondary">
                                    {formatTime(event.time)}
                                  </Typography.Text>
                                )}
                              </Space>
                              {payloadText && (
                                <div>
                                  <Typography.Text type="secondary">{payloadText}</Typography.Text>
                                </div>
                              )}
                            </div>
                          ),
                        };
                      })}
                    />
                  )}
                </div>

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
        </Col>
      </Row>
    </div>
  );
};

export default AgentTaskPanel;
