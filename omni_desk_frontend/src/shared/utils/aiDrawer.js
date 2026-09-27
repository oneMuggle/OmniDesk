/**
 * 全局 AI 抽屉唤起入口(S2)。
 *
 * 任何页面 / 卡片调用 openAIDrawer({ query }) 即可打开右下角智能助手抽屉;
 * 带 query 时抽屉打开后自动发送该问题。通过 window 自定义事件解耦,
 * 调用方不需要拿到抽屉组件的引用,也不依赖所在布局(App / AdminAppWrapper)。
 */
export const AI_DRAWER_EVENT = 'omnidesk:ai-drawer';

/**
 * @param {{ query?: string }} [options]
 */
export function openAIDrawer(options = {}) {
  const query = typeof options.query === 'string' ? options.query.trim() : '';
  window.dispatchEvent(new CustomEvent(AI_DRAWER_EVENT, { detail: { query } }));
}
