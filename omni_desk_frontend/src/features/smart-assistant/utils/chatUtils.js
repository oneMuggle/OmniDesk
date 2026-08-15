/**
 * 智能助手聊天页纯函数工具集。
 * 自 SmartChatPage.jsx 拆分(R3-D1)逐字搬运,不做语义改动。
 */

/**
 * 会话历史消息 → 页面展示消息（字段映射集中处理，
 * 复用于切换会话与 fork 后切入副本会话）。
 */
export const toDisplayMessages = (historyMessages) =>
  (historyMessages || []).map(msg => ({
    role: msg.role,
    content: msg.content,
    intent: msg.intent,
    tool_used: msg.tool_used,
    tool_result: msg.tool_result,
    sources: msg.sources,
    // 兼容:旧版会话历史无 log_id 时为 undefined,反馈仅记本地
    logId: msg.log_id,
  }));

/**
 * 解析内容中的 <thinking> 标签,分离思考内容与正文。
 * 支持多个 <thinking> 块(合并为一个 thinkContent)。
 */
export const parseThinkContent = (content) => {
  if (!content) return { mainContent: '', thinkContent: '' };

  const thinkRegex = /<thinking>([\s\S]*?)<\/thinking>/g;
  const thinkParts = [];
  let match;

  while ((match = thinkRegex.exec(content)) !== null) {
    const trimmed = match[1].trim();
    if (trimmed) thinkParts.push(trimmed);
  }

  if (thinkParts.length === 0) {
    return { mainContent: content, thinkContent: '' };
  }

  const mainContent = content.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').trim();
  return { mainContent, thinkContent: thinkParts.join('\n\n') };
};

/**
 * 解析 SSE 文本块,拆出所有 `data: <json>` 事件。
 */
export const parseSSE = (text) => {
  const lines = text.split('\n');
  const events = [];
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      try {
        events.push(JSON.parse(line.slice(6)));
      } catch {
        // 忽略解析失败
      }
    }
  }
  return events;
};
