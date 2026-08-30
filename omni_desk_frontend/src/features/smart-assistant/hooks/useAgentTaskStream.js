import { useCallback, useEffect, useRef, useState } from 'react';
import { interveneAgentTask, subscribeTaskStream } from '../api/agentTaskApi';
import mapAgentEvent from '../scenario/utils/mapAgentEvent';

const TERMINAL_TYPES = {
  'task.completed': 'completed',
  'task.failed': 'failed',
  'task.cancelled': 'cancelled',
  'task.partial': 'partial',
  completed: 'completed',
  partial: 'partial',
  failed: 'failed',
  cancelled: 'cancelled',
};
const RETRY_DELAYS = [1000, 2000, 4000];
const INTERVENTION_CONFIRM_TIMEOUT_MS = 5000;

export default function useAgentTaskStream(taskId, options = {}) {
  const { lastSeq: initialLastSeq = 0 } = options;
  const [events, setEvents] = useState([]);
  const [lastSeq, setLastSeq] = useState(initialLastSeq);
  const [status, setStatus] = useState(taskId ? 'running' : 'idle');
  const [error, setError] = useState(null);
  const subscriptionRef = useRef(null);
  const lastSeqRef = useRef(initialLastSeq);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef(null);
  const interventionTimerRef = useRef(null);
  const subscribeRef = useRef(null);
  const manuallyPausedRef = useRef(false);
  const pendingInterventionRef = useRef(null);
  const interventionTokenRef = useRef(0);

  const stop = useCallback(() => {
    if (subscriptionRef.current) {
      subscriptionRef.current.abort();
      subscriptionRef.current = null;
    }
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (interventionTimerRef.current) {
      clearTimeout(interventionTimerRef.current);
      interventionTimerRef.current = null;
    }
  }, []);

  const handleEvent = useCallback((event) => {
    if (event.sequence != null && event.sequence <= lastSeqRef.current) return;
    if (event.sequence != null) {
      lastSeqRef.current = event.sequence;
      setLastSeq(event.sequence);
    }
    const mappedEvent = mapAgentEvent(event);
    setEvents((previous) => [...previous, mappedEvent]);
    const eventStatus = event.payload?.status || event.status;
    const nextStatus = TERMINAL_TYPES[event.type] || TERMINAL_TYPES[eventStatus] || TERMINAL_TYPES[mappedEvent.type];
    if (eventStatus === 'partial') setStatus('partial');
    else if (nextStatus && event.type !== 'task.paused' && event.type !== 'task.resumed') setStatus(nextStatus);
    if (event.type === 'task.paused') {
      manuallyPausedRef.current = true;
      if (pendingInterventionRef.current?.action === 'pause') {
        pendingInterventionRef.current = null;
        if (interventionTimerRef.current) clearTimeout(interventionTimerRef.current);
        interventionTimerRef.current = null;
      }
      setStatus('paused');
    }
    if (event.type === 'task.resumed') {
      manuallyPausedRef.current = false;
      if (pendingInterventionRef.current?.action === 'resume') {
        pendingInterventionRef.current = null;
        if (interventionTimerRef.current) clearTimeout(interventionTimerRef.current);
        interventionTimerRef.current = null;
      }
      setStatus('running');
    }
  }, []);

  const subscribe = useCallback((showRunning = true) => {
    if (!taskId || manuallyPausedRef.current) return;
    stop();
    setError(null);
    if (showRunning) setStatus('running');
    subscriptionRef.current = subscribeTaskStream(taskId, {
      onEvent: handleEvent,
      onDone: (event, doneSequence) => {
        subscriptionRef.current = null;
        if (doneSequence != null && !event?.synthetic) {
          lastSeqRef.current = Math.max(lastSeqRef.current, doneSequence);
          setLastSeq(lastSeqRef.current);
        }
        const terminalStatus = event?.status;
        if (terminalStatus === 'paused') {
          manuallyPausedRef.current = true;
          setStatus('paused');
          return;
        }
        if (terminalStatus === 'partial' || terminalStatus === 'failed' || terminalStatus === 'cancelled') {
          setStatus(terminalStatus);
          return;
        }
        setStatus((current) => (current === 'running' ? 'completed' : current));
      },
      onTimeout: () => {
        const current = subscriptionRef.current;
        if (current) current.abort();
        subscriptionRef.current = null;
        retryCountRef.current = 0;
        retryTimerRef.current = setTimeout(() => subscribeRef.current?.(), 0);
      },
      onError: (streamError) => {
        const current = subscriptionRef.current;
        if (current) current.abort();
        subscriptionRef.current = null;
        const attempt = retryCountRef.current;
        if (attempt < RETRY_DELAYS.length) {
          retryCountRef.current += 1;
          retryTimerRef.current = setTimeout(() => subscribeRef.current?.(), RETRY_DELAYS[attempt]);
          return;
        }
        setError(streamError);
        setStatus('failed');
      },
    }, { lastSeq: lastSeqRef.current });
  }, [handleEvent, stop, taskId]);

  useEffect(() => {
    subscribeRef.current = subscribe;
  }, [subscribe]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial stream subscription synchronizes external SSE state
    subscribe();
    return stop;
  }, [stop, subscribe]);

  const intervene = useCallback(async (action) => {
    if (!taskId) return;
    const token = ++interventionTokenRef.current;
    pendingInterventionRef.current = { action, token };
    const previousStatus = action === 'pause' ? 'running' : 'paused';
    if (action === 'pause') manuallyPausedRef.current = false;
    if (action === 'pause') setStatus('pausing');
    if (action === 'resume') setStatus('resuming');
    try {
      await interveneAgentTask(taskId, action);
    } catch (interveneError) {
      manuallyPausedRef.current = false;
      setError(interveneError);
      setStatus(previousStatus);
      throw interveneError;
    }
    if (action === 'pause' || action === 'resume') {
      const previousStatus = action === 'pause' ? 'running' : 'paused';
      const pending = pendingInterventionRef.current;
      if (pending?.token !== token || pending.action !== action) return;
      pendingInterventionRef.current = null;
      interventionTimerRef.current = setTimeout(() => {
        if (interventionTokenRef.current !== token) return;
        pendingInterventionRef.current = null;
        interventionTimerRef.current = null;
        manuallyPausedRef.current = false;
        const timeoutError = new Error(`${action === 'pause' ? '暂停' : '恢复'}确认超时`);
        setError(timeoutError);
        setStatus(previousStatus);
      }, INTERVENTION_CONFIRM_TIMEOUT_MS);
      if (action === 'resume') {
        retryCountRef.current = 0;
        manuallyPausedRef.current = false;
        subscribe(false);
      }
      return;
    }
    if (action === 'cancel') {
      pendingInterventionRef.current = null;
      if (interventionTimerRef.current) clearTimeout(interventionTimerRef.current);
      interventionTimerRef.current = null;
      stop();
      setStatus('cancelled');
    }
  }, [stop, subscribe, taskId]);

  const retry = useCallback(() => {
    manuallyPausedRef.current = false;
    retryCountRef.current = 0;
    setError(null);
    // 后端没有 retry endpoint：只重新查看同一任务的后续事件，保留历史和 lastSeq。
    // 该动作不是重新执行，UI 文案使用“重新查看”避免误导。
    subscribe();
  }, [subscribe]);

  return {
    events, lastSeq, status, error,
    pause: () => intervene('pause'),
    resume: () => intervene('resume'),
    cancel: () => intervene('cancel'),
    retry, stop, onEvent: handleEvent,
  };
}
