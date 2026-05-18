import PropTypes from 'prop-types';
import './QuickCommands.css';

const DEFAULT_COMMANDS = [
  { label: '📅 明天谁值班？', query: '明天谁值班？' },
  { label: '👤 查找人员', query: '查找张三的信息' },
  { label: '📋 项目进度', query: '当前项目进度' },
  { label: '📝 备忘录', query: '我的备忘录' },
  { label: '📰 最新新闻', query: '最新新闻通知' },
  { label: '🔍 搜索文档', query: '搜索实验相关文档' },
];

const QuickCommands = ({ commands, onSend }) => {
  const items = commands || DEFAULT_COMMANDS;

  return (
    <div className="quick-commands">
      <div className="quick-commands-label">快捷指令</div>
      <div className="quick-commands-list">
        {items.map((cmd, idx) => (
          <button
            key={idx}
            className="quick-command-btn"
            onClick={() => onSend(cmd.query)}
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
      label: PropTypes.string.isRequired,
      query: PropTypes.string.isRequired,
    }),
  ),
  onSend: PropTypes.func.isRequired,
};
