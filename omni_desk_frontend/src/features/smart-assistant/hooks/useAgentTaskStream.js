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
  const subscribeRef = useRef(null);
  const manuallyPausedRef = useRef(false);

  const stop = useCallback(() => {
    if (subscriptionRef.current) {
      subscriptionRef.current.abort();
      subscriptionRef.current = null;
    }
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
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
    const nextStatus = TERMINAL_TYPES[event.type] || TERMINAL_TYPES[mappedEvent.type];
    if (nextStatus) setStatus(nextStatus);
    if (event.type === 'task.paused') setStatus('paused');
    if (event.type === 'task.resumed') {
      manuallyPausedRef.current = false;
      setStatus('running');
    }
  }, []);

  const subscribe = useCallback(() => {
    if (!taskId || manuallyPausedRef.current) return;
    stop();
    setError(null);
    setStatus('running');
    subscriptionRef.current = subscribeTaskStream(taskId, {
      onEvent: handleEvent,
      onDone: (event, doneSequence) => {
        subscriptionRef.current = null;
        if (doneSequence != null) {
          lastSeqRef.current = Math.max(lastSeqRef.current, doneSequence);
          setLastSeq(lastSeqRef.current);
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
    subscribe();
    return stop;
  }, [stop, subscribe]);

  const intervene = useCallback(async (action) => {
    if (!taskId) return;
    if (action === 'pause') manuallyPausedRef.current = true;
    await interveneAgentTask(taskId, action);
    if (action === 'pause') {
      stop();
      setStatus('paused');
    } else if (action === 'resume') {
      manuallyPausedRef.current = false;
      retryCountRef.current = 0;
      subscribe();
    } else if (action === 'cancel') {
      stop();
      setStatus('cancelled');
    }
  }, [stop, subscribe, taskId]);

  const retry = useCallback(() => {
    manuallyPausedRef.current = false;
    retryCountRef.current = 0;
    setEvents([]);
    setError(null);
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
