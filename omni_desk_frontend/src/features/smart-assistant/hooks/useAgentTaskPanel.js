/**
 * useAgentTaskPanel — AgentTaskPanel 全部业务逻辑 HookLayer
 *
 * 由 AgentTaskPanel.jsx 拆分而来,承接全部 state/refs/handler/effect:
 * 任务列表加载、创建并执行、任务详情时间线、SSE 实时订阅、人工介入。
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { message } from 'antd';
import {
  TASK_STATUS_MAP,
  createAgentTask,
  executeAgentTask,
  getAgentTasks,
  getAgentTaskTimeline,
  interveneAgentTask,
  subscribeTaskStream,
} from '../api/agentTaskApi';
import { TERMINAL_STATUSES, normalizeHistoryEvent, normalizeStreamEvent, statusInfoOf } from '../utils/agentTaskUtils';

const useAgentTaskPanel = () => {
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

  return {
    tasks, tasksLoading, tasksError,
    goal, setGoal, createLoading, createError,
    selectedTaskId, taskDetail, subtasks, events,
    detailLoading, detailError, streaming, streamError,
    interveneLoading,
    loadTasks, handleSelectTask, handleCreateAndExecute, handleIntervene,
  };
};

export default useAgentTaskPanel;
