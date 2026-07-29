/**
 * 会话 fork / Markdown 导出 API（SmartChatPage 专用）。
 *
 * 为避免与共享 smartAssistantApi.js 的并行开发冲突，
 * 本任务所需请求函数独立放在页面同目录。
 */
import apiClient from '../../../shared/api/apiClient';

const BASE_URL = 'smart-assistant';

/**
 * 复制会话（fork）。
 *
 * POST /api/smart-assistant/sessions/{id}/fork/
 * @param {number|string} sessionId 源会话 ID
 * @param {{ atMessage?: number, title?: string }} [options]
 *   - atMessage: 仅复制前 N 条消息（缺省全量复制）
 *   - title: 新会话标题（缺省「原标题（副本）」）
 * @returns {Promise<{ data: object }>} axios 响应，data 为新会话序列化
 */
export async function forkSession(sessionId, { atMessage, title } = {}) {
  const body = {};
  if (atMessage !== undefined && atMessage !== null) {
    body.at_message = atMessage;
  }
  if (title) {
    body.title = title;
  }
  return apiClient.post(`${BASE_URL}/sessions/${sessionId}/fork/`, body);
}

/**
 * 读取访问令牌（与 sendSmartChatStream 的取值方式一致）。
 * @returns {string|undefined} JWT access token
 */
function getAccessToken() {
  const raw = localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}';
  try {
    return JSON.parse(raw).access;
  } catch {
    return undefined;
  }
}

/**
 * 从 Content-Disposition 解析下载文件名（支持 RFC 5987 filename*）。
 * 解析失败时返回 fallback。
 * @param {Response} response fetch 响应
 * @param {string} fallback 兜底文件名
 * @returns {string}
 */
export function parseDownloadFilename(response, fallback) {
  const disposition = response.headers?.get?.('Content-Disposition') || '';
  // 优先 RFC 5987 编码的 filename*=UTF-8''<percent-encoded>
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1].trim());
    } catch {
      // 解码失败继续尝试普通 filename
    }
  }
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (plainMatch && plainMatch[1].trim()) {
    return plainMatch[1].trim();
  }
  return fallback;
}

/** 生成本地兜底文件名：<标题>-<日期>.md */
function buildFallbackFilename(title) {
  const safeTitle = (title || '会话').replace(/[\\/:*?"<>|\r\n\t]+/g, '_');
  const now = new Date();
  const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(
    now.getDate()
  ).padStart(2, '0')}`;
  return `${safeTitle}-${dateStr}.md`;
}

/** 通过临时 <a> 触发浏览器 blob 下载 */
function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/**
 * 导出会话为 Markdown 文件（fetch + blob 下载，携带 Authorization）。
 *
 * GET /api/smart-assistant/sessions/{id}/export/
 * @param {number|string} sessionId 会话 ID
 * @param {string} [title] 会话标题，用于服务端未提供文件名时的兜底命名
 * @throws {Error} 非 2xx 响应时抛出（页面层统一 message.error）
 */
export async function exportSessionMarkdown(sessionId, title) {
  const response = await fetch(
    `${apiClient.defaults.baseURL}${BASE_URL}/sessions/${sessionId}/export/`,
    {
      method: 'GET',
      headers: { Authorization: `Bearer ${getAccessToken()}` },
    }
  );

  if (response.status === 401) {
    throw new Error('认证已过期，请重新登录');
  }
  if (!response.ok) {
    throw new Error('导出失败，请稍后重试');
  }

  const blob = await response.blob();
  const filename = parseDownloadFilename(response, buildFallbackFilename(title));
  triggerBlobDownload(blob, filename);
}
