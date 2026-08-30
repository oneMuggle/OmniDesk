/**
 * 多 Agent 任务 API 模块
 *
 * 对接后端 smart_assistant.views.tasks.AgentTaskViewSet
 * (router basename: agent-tasks, 挂载于 /api/smart-assistant/tasks/):
 * - GET    /api/smart-assistant/tasks/                      任务列表
 * - POST   /api/smart-assistant/tasks/create/               用户查询 → Supervisor 分解 → 创建任务
 * - POST   /api/smart-assistant/tasks/{id}/execute/         触发执行(异步 Celery)
 * - POST   /api/smart-assistant/tasks/{id}/intervene/       人工介入 {action: pause|resume|cancel}
 * - GET    /api/smart-assistant/tasks/{id}/timeline/        完整时间线 {task, subtasks, timeline}
 * - GET    /api/smart-assistant/tasks/{id}/stream/          SSE 实时进度
 *
 * SSE 事件格式: `data: {type, sequence, subtask_id, payload, timestamp}\n\n`
 * 终态事件: `{type: 'done', task_id}` / `{type: 'timeout'}` (服务端 60 秒轮询超时)
 */
import apiClient from '../../../shared/api/apiClient';

const BASE_URL = 'smart-assistant/tasks';

/**
 * 主任务状态 → AntD Tag 颜色 + 中文文案
 * (与后端 AgentTask.STATUS_CHOICES 对齐)
 */
export const TASK_STATUS_MAP = {
  pending: { label: '待执行', color: 'default' },
  running: { label: '执行中', color: 'processing' },
  paused: { label: '已暂停', color: 'warning' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '已失败', color: 'error' },
  cancelled: { label: '已取消', color: 'default' },
};

/**
 * 子任务状态 → AntD Tag 颜色 + 中文文案
 * (与后端 AgentSubTask.STATUS_CHOICES 对齐)
 */
export const SUBTASK_STATUS_MAP = {
  pending: { label: '待执行', color: 'default' },
  running: { label: '执行中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '已失败', color: 'error' },
  skipped: { label: '已跳过', color: 'default' },
};

/**
 * 事件类型 → 中文文案(与后端 AgentEvent.EVENT_TYPE_CHOICES 对齐)
 */
export const EVENT_TYPE_LABELS = {
  'task.started': '任务开始',
  'task.paused': '任务暂停',
  'task.resumed': '任务恢复',
  'task.completed': '任务完成',
  'task.failed': '任务失败',
  'task.cancelled': '任务取消',
  'subtask.started': '子任务开始',
  'subtask.progress': '子任务进度',
  'subtask.tool_call': '子任务工具调用',
  'subtask.quality_gate': '子任务质量门禁',
  'subtask.completed': '子任务完成',
  'subtask.failed': '子任务失败',
  'supervisor.decision': 'Supervisor 决策',
  'supervisor.intervention': 'Supervisor 介入',
  'user.intervention': '用户介入',
  'hook.triggered': 'Hook 触发',
};

/**
 * 获取当前用户的任务列表(按创建时间倒序)
 */
export async function getAgentTasks() {
  return apiClient.get(`${BASE_URL}/`);
}

/**
 * 获取任务完整时间线: {task, subtasks, timeline}
 */
export async function getAgentTaskTimeline(taskId) {
  return apiClient.get(`${BASE_URL}/${taskId}/timeline/`);
}

/**
 * 创建任务: 用户查询 → Supervisor 分解 → 创建 AgentTask + SubTasks
 * @param {string} query 用户的任务目标描述
 * @param {object} [userContext] 可选的用户上下文
 * @returns 201 {task_id, status, plan}
 */
export async function createAgentTask(query, userContext = {}) {
  return apiClient.post(`${BASE_URL}/create/`, {
    query,
    user_context: userContext,
  });
}

/**
 * 触发任务执行(仅 pending 状态可执行,后端异步 Celery)
 */
export async function executeAgentTask(taskId) {
  return apiClient.post(`${BASE_URL}/${taskId}/execute/`);
}

/**
 * 人工介入
 * @param {string} taskId 任务 ID
 * @param {'pause'|'resume'|'cancel'} action 介入动作
 */
export async function interveneAgentTask(taskId, action) {
  return apiClient.post(`${BASE_URL}/${taskId}/intervene/`, { action });
}

/**
 * 订阅任务 SSE 实时进度流(原生 fetch + Bearer token,参考 smartAssistantApi.sendSmartChatStream)
 *
 * 服务端每次连接从 sequence=0 回放全部事件,60 秒无终态后发送 timeout 事件并关闭连接 —
 * 调用方可据 onTimeout 决定是否重新订阅(重连产生的重复事件由调用方按 sequence 去重)。
 *
 * @param {string} taskId 任务 ID
 * @param {object} callbacks
 * @param {(event: object) => void} [callbacks.onEvent] 普通进度事件 {type, sequence, subtask_id, payload, timestamp}
 * @param {(event?: object) => void} [callbacks.onDone] 收到 done 事件或服务端正常关闭流
 * @param {() => void} [callbacks.onTimeout] 服务端 60 秒轮询超时(任务可能仍在运行)
 * @param {(error: Error) => void} [callbacks.onError] 连接/认证/解析错误
 * @returns {{ abort: () => void }} 调用 abort() 断开 SSE 连接
 */
export function subscribeTaskStream(taskId, callbacks = {}, options = {}) {
  const { onEvent, onDone, onTimeout, onError } = callbacks;
  const { lastSeq = 0 } = options;
  const abortController = new AbortController();

  const run = async () => {
    const authTokens = JSON.parse(
      localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}'
    );
    const token = authTokens.access;

    let response;
    try {
      const streamUrl = `${apiClient.defaults.baseURL}${BASE_URL}/${taskId}/stream/${lastSeq ? `?last_seq=${encodeURIComponent(lastSeq)}` : ''}`;
      response = await fetch(streamUrl, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        signal: abortController.signal,
      });
    } catch (error) {
      if (error.name === 'AbortError') {
        // 调用方主动断开,不视为错误
        return;
      }
      onError?.(new Error('网络连接失败，请检查网络'));
      return;
    }

    if (response.status === 401) {
      onError?.(new Error('认证已过期，请重新登录'));
      return;
    }
    if (!response.ok) {
      onError?.(new Error('任务进度流连接失败'));
      return;
    }

    let sequence = lastSeq;
    let timedOut = false;
    if (!response.body || typeof response.body.getReader !== 'function') {
      const timeline = await getAgentTaskTimeline(taskId);
      const events = timeline.data?.timeline || [];
      events.forEach((event) => {
        if (event.sequence != null && event.sequence <= sequence) return;
        if (event.sequence != null) sequence = event.sequence;
        onEvent?.(event);
      });
      onDone?.(undefined, sequence);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        let sawDone = false;
        parts.forEach((part) => {
          const line = part.trim();
          if (!line.startsWith('data:')) return;
          const jsonText = line.slice(5).trim();
          if (!jsonText) return;

          let event;
          try {
            event = JSON.parse(jsonText);
          } catch {
            return;
          }

          if (event.type === 'done') {
            onDone?.(event, sequence);
            sawDone = true;
            return;
          }
          if (event.type === 'timeout') {
            timedOut = true;
            onTimeout?.(event);
            return;
          }
          if (event.sequence != null && event.sequence <= sequence) return;
          if (event.sequence != null) sequence = event.sequence;
          onEvent?.(event);
        });
        if (sawDone) return;
      }
      // 服务端正常关闭连接(未显式发送 done)
      if (!timedOut) onDone?.(undefined, sequence);
    } catch (error) {
      if (error.name === 'AbortError') {
        return;
      }
      onError?.(error);
    }
  };

  run();

  return {
    abort: () => abortController.abort(),
  };
}
