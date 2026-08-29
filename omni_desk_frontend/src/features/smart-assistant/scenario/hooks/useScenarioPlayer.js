// 剧本播放器：维护当前剧本的推进状态与事件流
// 不接后端：用 setTimeout 按 step.delayAfter 推进
import { useCallback, useEffect, useReducer, useRef } from 'react';
import { getScenario } from '../data/scenarios';

/**
 * @typedef {Object} PlayerEvent
 * @property {string} id          本次事件唯一 id
 * @property {string} scenarioId
 * @property {number} stepIndex   对应剧本 steps 数组下标
 * @property {('thinking'|'tool_call'|'tool_result'|'final_answer')} type
 * @property {number} ts          Date.now()
 * @property {string} [agent]
 * @property {string} [tool]
 * @property {string} [content]
 * @property {Record<string, unknown>} [input]
 * @property {unknown} [output]
 * @property {string} [payloadKind]
 * @property {Record<string, unknown>} [payload]
 *
 * @typedef {Object} PlayerState
 * @property {string|null} activeScenarioId
 * @property {PlayerEvent[]} events
 * @property {('idle'|'running'|'paused'|'completed')} status
 * @property {number} cursor
 * @property {string|null} userInput
 */

/** @type {PlayerState} */
const initialState = {
  activeScenarioId: null,
  events: [],
  status: 'idle',
  cursor: 0,
  userInput: null,
};

let eventSeq = 0;
function nextEventId() {
  eventSeq += 1;
  return `evt-${Date.now().toString(36)}-${eventSeq}`;
}

function reducer(state, action) {
  switch (action.type) {
    case 'START': {
      return {
        ...initialState,
        activeScenarioId: action.scenarioId,
        status: 'running',
        userInput: action.userInput || null,
      };
    }
    case 'APPEND_EVENT': {
      return {
        ...state,
        events: [...state.events, action.event],
        cursor: action.cursor ?? state.cursor + 1,
      };
    }
    case 'PAUSE': {
      if (state.status !== 'running') return state;
      return { ...state, status: 'paused' };
    }
    case 'RESUME': {
      if (state.status !== 'paused') return state;
      return { ...state, status: 'running' };
    }
    case 'COMPLETE': {
      return { ...state, status: 'completed' };
    }
    case 'RESET': {
      return initialState;
    }
    default:
      return state;
  }
}

/**
 * @param {{ autoStartInterval?: number }} [options]
 */
export function useScenarioPlayer(options = {}) {
  const { autoStartInterval = 0 } = options;
  const [state, dispatch] = useReducer(reducer, initialState);
  const timerRef = useRef(null);
  const cursorRef = useRef(0);
  const scenarioIdRef = useRef(null);
  const tickRef = useRef(null);

  // keep refs synced so setTimeout callbacks see latest values
  useEffect(() => {
    cursorRef.current = state.cursor;
  }, [state.cursor]);
  useEffect(() => {
    scenarioIdRef.current = state.activeScenarioId;
  }, [state.activeScenarioId]);

  const cancel = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const pushEvent = useCallback((scenarioId, stepIndex, step) => {
    /** @type {PlayerEvent} */
    const event = {
      id: nextEventId(),
      scenarioId,
      stepIndex,
      ts: Date.now(),
      ...step,
    };
    dispatch({ type: 'APPEND_EVENT', event, cursor: cursorRef.current + 1 });
  }, []);

  const tick = useCallback(() => {
    const sid = scenarioIdRef.current;
    if (!sid) return;
    const scenario = getScenario(sid);
    if (!scenario) return;
    const idx = cursorRef.current;
    if (idx >= scenario.steps.length) {
      dispatch({ type: 'COMPLETE' });
      return;
    }
    const step = scenario.steps[idx];
    pushEvent(sid, idx, step);
    const delay = step.delayAfter ?? 800;
    if (idx === scenario.steps.length - 1) {
      // 末步后再走 600ms 让用户看到 final_answer
      timerRef.current = setTimeout(() => {
        dispatch({ type: 'COMPLETE' });
      }, 600);
      return;
    }
    timerRef.current = setTimeout(
      () => tickRef.current && tickRef.current(),
      delay
    );
  }, [pushEvent]);

  // 让 tickRef 在 commit 之后指向最新 tick,避免 setTimeout 闭包过期
  useEffect(() => {
    tickRef.current = tick;
  }, [tick]);

  const start = useCallback(
    (scenarioId, userInput) => {
      cancel();
      eventSeq = 0;
      dispatch({ type: 'START', scenarioId, userInput });
      cursorRef.current = 0;
      scenarioIdRef.current = scenarioId;
      // 第一帧先渲染
      if (autoStartInterval <= 0) {
        // 立刻触发首步
        const scenario = getScenario(scenarioId);
        if (scenario && scenario.steps.length > 0) {
          const first = scenario.steps[0];
          pushEvent(scenarioId, 0, first);
          const delay = first.delayAfter ?? 800;
          // 把 cursor 推进后再启动 tick
          cursorRef.current = 1;
          timerRef.current = setTimeout(
            () => tickRef.current && tickRef.current(),
            delay
          );
        }
      } else {
        timerRef.current = setTimeout(
          () => tickRef.current && tickRef.current(),
          autoStartInterval
        );
      }
    },
    [autoStartInterval, cancel, pushEvent]
  );

  const pause = useCallback(() => {
    cancel();
    dispatch({ type: 'PAUSE' });
  }, [cancel]);

  const resume = useCallback(() => {
    if (!scenarioIdRef.current) return;
    dispatch({ type: 'RESUME' });
    timerRef.current = setTimeout(
      () => tickRef.current && tickRef.current(),
      100
    );
  }, []);

  const reset = useCallback(() => {
    cancel();
    dispatch({ type: 'RESET' });
    cursorRef.current = 0;
    scenarioIdRef.current = null;
  }, [cancel]);

  useEffect(() => () => cancel(), [cancel]);

  return {
    state,
    start,
    pause,
    resume,
    reset,
  };
}

export default useScenarioPlayer;
