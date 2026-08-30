import { useCallback, useEffect, useRef, useState } from 'react';
import { interveneAgentTask, subscribeTaskStream } from '../api/agentTaskApi';

const TERMINAL_TYPES = {
  'task.completed': 'completed',
  'task.failed': 'failed',
  'task.cancelled': 'cancelled',
};

export default function useAgentTaskStream(taskId, options = {}) {
  const { lastSeq: initialLastSeq = 0 } = options;
  const [events, setEvents] = useState([]);
  const [lastSeq, setLastSeq] = useState(initialLastSeq);
  const [status, setStatus] = useState(taskId ? 'running' : 'idle');
  const [error, setError] = useState(null);
  const subscriptionRef = useRef(null);
  const lastSeqRef = useRef(initialLastSeq);

  const stop = useCallback(() => {
    if (subscriptionRef.current) {
      subscriptionRef.current.abort();
      subscriptionRef.current = null;
    }
  }, []);

  const handleEvent = useCallback((event) => {
    if (event.sequence != null && event.sequence <= lastSeqRef.current) return;
    if (event.sequence != null) {
      lastSeqRef.current = event.sequence;
      setLastSeq(event.sequence);
    }
    setEvents((previous) => [...previous, event]);
    if (TERMINAL_TYPES[event.type]) setStatus(TERMINAL_TYPES[event.type]);
  }, []);

  const subscribe = useCallback(() => {
    if (!taskId) return;
    stop();
    setError(null);
    setStatus('running');
    subscriptionRef.current = subscribeTaskStream(taskId, {
      onEvent: handleEvent,
      onDone: () => {
        subscriptionRef.current = null;
        setStatus((current) => (current === 'running' ? 'completed' : current));
      },
      onTimeout: () => {
        subscriptionRef.current = null;
        setStatus('paused');
      },
      onError: (streamError) => {
        subscriptionRef.current = null;
        setError(streamError);
        setStatus('failed');
      },
    }, { lastSeq: lastSeqRef.current });
  }, [handleEvent, stop, taskId]);

  useEffect(() => {
    subscribe();
    return stop;
  }, [stop, subscribe]);

  const intervene = useCallback(async (action) => {
    if (!taskId) return;
    await interveneAgentTask(taskId, action);
    if (action === 'pause') {
      stop();
      setStatus('paused');
    } else if (action === 'resume') {
      subscribe();
    } else if (action === 'cancel') {
      stop();
      setStatus('cancelled');
    }
  }, [stop, subscribe, taskId]);

  const retry = useCallback(() => {
    setEvents([]);
    setError(null);
    subscribe();
  }, [subscribe]);

  return {
    events,
    lastSeq,
    status,
    error,
    pause: () => intervene('pause'),
    resume: () => intervene('resume'),
    cancel: () => intervene('cancel'),
    retry,
    stop,
    onEvent: handleEvent,
  };
}
