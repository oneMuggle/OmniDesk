import { createAgentTask, executeAgentTask } from '../api/agentTaskApi';
import { matchScenarioByInput } from '../scenario/data/scenarios';

/**
 * 创建并启动一个多 Agent 协作任务,返回可直接插入消息列表的协作卡片消息。
 *
 * 完整页(useSmartChat)与 AI 抽屉(QuickAssistant)共用:任务计划卡点击
 * 「创建协作任务」、场景快捷按钮(mode: 'agent')都走这里。卡片组件
 * ScenarioCollabCard 内部按 taskId 订阅 SSE 进度。
 *
 * @param {string} query 任务目标
 * @param {{ conversationId?: number|string|null, onCreated?: (card: object) => void }} [options]
 *   onCreated 在任务创建成功、开始执行之前回调,调用方可借此先把卡片放进消息列表
 * @returns {Promise<object>} 协作卡片消息 { id, role, type: 'collab_card', taskId, ... }
 * @throws 创建失败(无 task_id)或执行请求失败时抛出
 */
export async function startAgentTask(query, options = {}) {
  const { conversationId = null, onCreated } = options;
  const created = await createAgentTask(query, { conversation_id: conversationId });
  const task = created?.data || {};
  const taskId = task.task_id;
  if (!taskId) throw new Error('任务创建失败');
  const matchedScenario = matchScenarioByInput(query);
  const card = {
    id: `agent-${taskId}`,
    role: 'assistant',
    type: 'collab_card',
    taskId,
    scenarioId: matchedScenario?.id || null,
    userInput: query,
    objective: task.plan?.objective || query,
  };
  if (typeof onCreated === 'function') onCreated(card);
  await executeAgentTask(taskId);
  return card;
}
