import PropTypes from 'prop-types';
import './QuickCommands.css';

const DEFAULT_COMMANDS = [
  { label: '📅 明天谁值班？', query: '明天谁值班？' },
  { label: '👤 查找人员', query: '查找张三的信息' },
  { label: '📋 项目进度', query: '当前项目进度' },
  { label: '📝 备忘录', query: '我的备忘录' },
  { label: '📰 最新新闻', query: '最新新闻通知' },
  { label: '🔍 搜索文档', query: '搜索实验相关文档' },
  {
    key: 'personal_summary_week',
    label: '我的本周',
    intent: 'personal_summary',
    scope: 'week',
  },
  {
    key: 'personal_summary_today',
    label: '我今天',
    intent: 'personal_summary',
    scope: 'today',
  },
];

/**
 * 把 {intent, scope} 翻译为自然语言 query。
 * Task 17 fix C4: 后端 SmartChatRequestSerializer 不接受 intent/scope 字段,
 * 选择前端翻译为 query 字符串走原链路(方案 B)。
 */
const translateIntentToQuery = ({ intent, scope }) => {
  if (intent === 'personal_summary') {
    if (scope === 'today') return '今天有什么安排';
    if (scope === 'week') return '这周我有哪些事';
    if (scope === 'month') return '这个月我有哪些事';
    return '我有哪些事';
  }
  // 未知 intent 兜底:用 scope 拼一个最简 query
  return scope ? `我的${scope}` : '请帮我汇总';
};

const QuickCommands = ({ commands, onSend, onCommand }) => {
  const items = commands || DEFAULT_COMMANDS;

  const handleClick = (cmd) => {
    // Task 17: 优先把 {intent, scope} 翻译为自然语言 query 走 onSend。
    // 保留 onCommand 兼容旧调用方(若父组件同时提供 onCommand,仍按原方式透传)。
    if (cmd.intent) {
      const translated = cmd.query || translateIntentToQuery({ intent: cmd.intent, scope: cmd.scope });
      if (typeof onSend === 'function') {
        onSend(translated);
        return;
      }
      if (typeof onCommand === 'function') {
        onCommand({ intent: cmd.intent, scope: cmd.scope });
        return;
      }
      return;
    }
    if (cmd.query && typeof onSend === 'function') {
      onSend(cmd.query);
    }
  };

  return (
    <div className="quick-commands">
      <div className="quick-commands-label">快捷指令</div>
      <div className="quick-commands-list">
        {items.map((cmd, idx) => (
          <button
            key={cmd.key || idx}
            className="quick-command-btn"
            onClick={() => handleClick(cmd)}
          >
            {cmd.label}
          </button>
        ))}
      </div>
    </div>
  );
};

export default QuickCommands;

QuickCommands.propTypes = {
  commands: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string,
      label: PropTypes.string.isRequired,
      query: PropTypes.string,
      intent: PropTypes.string,
      scope: PropTypes.string,
    }),
  ),
  onSend: PropTypes.func,
  onCommand: PropTypes.func,
};