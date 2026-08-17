import { isDev } from './env';
import { getEnv } from './env';

const SENSITIVE_KEY_PATTERN = /(password|passwd|token|refresh|secret|authorization|cookie|session|api[_-]?key)/i;
const ALLOWED_KEYS = ['kind', 'message', 'stack', 'source', 'url', 'ua', 'extra', 'request_id'];
const API_BASE = getEnv('VITE_API_BASE_URL', '/api');

// 截断长度上限(stack 更长因含完整调用栈,其他 500 字符够用)
const TRUNCATE = { stack: 5000, default: 500 };

/**
 * 服务端兜底脱敏(白名单 + 嵌套敏感键清理)。即便前端被改坏或恶意构造 payload,
 * 后端 core/api.py:_sanitize_client_error_payload 会再做一次同样的处理。
 * 重复一次是 defense in depth,不是冗余。
 */
function sanitizeReport(payload) {
  if (!payload || typeof payload !== 'object') return {};
  const out = {};
  for (const key of ALLOWED_KEYS) {
    if (!(key in payload)) continue;
    const val = payload[key];
    if (typeof val === 'string') {
      out[key] = val.slice(0, TRUNCATE[key] || TRUNCATE.default);
    } else if (val && typeof val === 'object' && key === 'extra') {
      // 递归清敏感键
      const cleanExtra = {};
      for (const [ek, ev] of Object.entries(val)) {
        if (!SENSITIVE_KEY_PATTERN.test(ek)) cleanExtra[ek] = ev;
      }
      out[key] = cleanExtra;
    } else if (val != null) {
      out[key] = val;
    }
  }
  return out;
}

/**
 * 上报浏览器侧错误到后端 /api/system/client-error/。
 * 用 navigator.sendBeacon 优先(页面卸载时不丢包),fallback fetch keepalive。
 * 失败静默(端点自身被 throttle 时不应抛错打断业务)。
 */
function report(payload) {
  try {
    const cleaned = sanitizeReport({
      ...payload,
      ua: typeof navigator !== 'undefined' ? navigator.userAgent : '',
      url: typeof window !== 'undefined' ? window.location.href : '',
    });
    const body = JSON.stringify(cleaned);
    const endpoint = `${API_BASE}/system/client-error/`;

    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon(endpoint, blob);
      return;
    }
    if (typeof fetch !== 'undefined') {
      fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => {});
    }
  } catch {
    // 静默失败:logger 自己不能抛错
  }
}

export const logger = {
  debug: (...args) => isDev && console.debug('[OmniDesk]', ...args),
  info: (...args) => console.info('[OmniDesk]', ...args),
  warn: (...args) => console.warn('[OmniDesk]', ...args),
  error: (...args) => console.error('[OmniDesk]', ...args),
  report,
  sanitizeReport,
};
