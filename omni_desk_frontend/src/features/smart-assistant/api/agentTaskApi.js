import apiClient from '../../../shared/api/apiClient';
import { authFetch } from '../../../shared/api/authFetch';
import { readAuthTokens } from '../../../shared/utils/authTokens';

const BASE_URL = 'smart-assistant/tasks';
const FALLBACK_POLL_INTERVAL_MS = 2000;
const FALLBACK_MAX_POLLS = 30;
const TERMINAL_TASK_STATUSES = ['completed', 'partial', 'failed', 'cancelled', 'paused'];

export const TASK_STATUS_META = {
  pending: { color: 'default', label: '等待中' }, running: { color: 'processing', label: '执行中' },
  pausing: { color: 'warning', label: '暂停中' }, paused: { color: 'warning', label: '已暂停' },
  resuming: { color: 'processing', label: '恢复中' }, completed: { color: 'success', label: '已完成' },
  partial: { color: 'warning', label: '部分完成' }, failed: { color: 'error', label: '执行失败' },
  cancelled: { color: 'default', label: '已取消' },
};

export async function getAgentTasks() { return apiClient.get(`${BASE_URL}/`); }
export async function getAgentTask(taskId) { return apiClient.get(`${BASE_URL}/${taskId}/`); }
export async function getAgentTaskTimeline(taskId, config) {
  const url = `${BASE_URL}/${taskId}/timeline/`;
  return config ? apiClient.get(url, config) : apiClient.get(url);
}
export async function createAgentTask(query, userContext = {}) {
  return apiClient.post(`${BASE_URL}/create/`, { query, user_context: userContext });
}
export async function executeAgentTask(taskId) { return apiClient.post(`${BASE_URL}/${taskId}/execute/`); }
export async function interveneAgentTask(taskId, action) {
  return apiClient.post(`${BASE_URL}/${taskId}/intervene/`, { action });
}

function isAbortError(error) { return error && (error.name === 'AbortError' || error.code === 'ERR_CANCELED'); }
function normaliseSequence(value, fallback) {
  const sequence = Number(value);
  return Number.isFinite(sequence) && sequence >= 0 ? sequence : fallback;
}

export function subscribeTaskStream(taskId, callbacks = {}, options = {}) {
  const { onEvent, onDone, onTimeout, onError } = callbacks;
  let sequence = normaliseSequence(options.lastSeq, 0);
  let stopped = false;
  let pollTimer = null;
  let pollCount = 0;
  const hasAbortController = typeof AbortController === 'function';
  const abortController = hasAbortController ? new AbortController() : {
    signal: { aborted: false, addEventListener: function () {} },
    abort: function () { this.signal.aborted = true; },
  };

  const stop = () => {
    stopped = true;
    if (pollTimer !== null) { clearTimeout(pollTimer); pollTimer = null; }
    if (abortController) abortController.abort();
  };
  const dispatch = (event) => {
    if (!event || event.sequence == null) { onEvent?.(event); return true; }
    const eventSequence = Number(event.sequence);
    if (!Number.isFinite(eventSequence) || eventSequence <= sequence) return false;
    sequence = eventSequence;
    onEvent?.(event);
    return true;
  };
  const pollTimeline = async () => {
    if (stopped) return;
    if (pollCount >= FALLBACK_MAX_POLLS) {
      onTimeout?.({ type: 'timeout', task_id: taskId, sequence }); stop(); return;
    }
    pollCount += 1;
    try {
      const response = await getAgentTaskTimeline(taskId, { signal: abortController.signal });
      if (stopped) return;
      const data = response?.data || {};
      const events = Array.isArray(data.timeline) ? data.timeline.slice() : [];
      events.sort((a, b) => normaliseSequence(a?.sequence, 0) - normaliseSequence(b?.sequence, 0));
      events.forEach(dispatch);
      const status = data.task && data.task.status;
      if (TERMINAL_TASK_STATUSES.indexOf(status) !== -1) {
        const done = { type: 'done', task_id: taskId, status, sequence };
        stop(); onDone?.(done); return;
      }
      pollTimer = setTimeout(pollTimeline, FALLBACK_POLL_INTERVAL_MS);
    } catch (error) {
      if (stopped || isAbortError(error)) return;
      stop(); onError?.(error);
    }
  };
  const runSse = async () => {
    const token = readAuthTokens()?.access;
    if (!token) { onError?.(new Error('认证已过期，请重新登录')); return; }
    if (!hasAbortController) { pollTimeline(); return; }
    const query = sequence ? `?last_seq=${encodeURIComponent(sequence)}` : '';
    let response;
    try {
      response = await authFetch(`${apiClient.defaults.baseURL}${BASE_URL}/${taskId}/stream/${query}`, {
        method: 'GET', signal: abortController.signal,
      });
    } catch (error) {
      if (!stopped && !isAbortError(error)) onError?.(error); return;
    }
    if (stopped) return;
    if (response.ok === false) { onError?.(new Error(response.status === 401 ? '认证已过期，请重新登录' : '任务进度流连接失败')); return; }
    if (!response.body || typeof response.body.getReader !== 'function') { pollTimeline(); return; }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finished = false;
    try {
      while (!stopped && !finished) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const parts = buffer.split('\n\n'); buffer = parts.pop() || '';
        parts.forEach((part) => {
          const line = part.trim().split('\n').find((item) => item.startsWith('data:'));
          if (!line) return;
          let event;
          try { event = JSON.parse(line.slice(5).trim()); } catch (error) { return; }
          if (event.type === 'done') {
            if (event.sequence != null) sequence = normaliseSequence(event.sequence, sequence);
            finished = true; onDone?.({ ...event, sequence }, sequence); return;
          }
          if (event.type === 'timeout') { finished = true; onTimeout?.(event); return; }
          dispatch(event);
        });
      }
      if (!stopped && !finished) onDone?.(undefined, sequence);
    } catch (error) {
      if (!stopped && !isAbortError(error)) onError?.(error);
    } finally { if (reader.releaseLock) reader.releaseLock(); }
  };
  runSse();
  return { abort: stop };
}
