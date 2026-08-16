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

/**
 * 消费 SSE ReadableStream:解析出 JSON 事件,逐个交给 onEvent 处理。
 * R4-B2 提取自 QuickAssistant 与 useSmartChat.runStream 中重复的流式读取循环,
 * 收敛为单一共享实现。
 *
 * @param {ReadableStream} stream 服务端 SSE 响应体
 * @param {(event: object) => (void | Promise<*> | boolean)} onEvent 每个解析出的事件回调;
 *   返回 false 立即中止读取(丢弃剩余 buffer)。
 * @param {object} [opts]
 * @param {() => void} [opts.onBeforeRead] 每次 reader.read() 之前调用
 *   (用于重置超时计时等;done 前的最后一次 read 也会触发,消费方需自行在收尾清理)
 * @returns {Promise<void>}
 */
export async function consumeSSEStream(stream, onEvent, { onBeforeRead } = {}) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (onBeforeRead) onBeforeRead();
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';

    for (const part of parts) {
      const events = parseSSE(part);
      for (const event of events) {
        const result = onEvent(event);
        // 支持 async onEvent(如 useSmartChat.handleSSEEvent 返回会话 ID)
        if (result === false) return;
        await result;
      }
    }
  }
}
