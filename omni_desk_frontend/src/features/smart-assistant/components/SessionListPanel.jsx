import { Dropdown } from 'antd';
import PropTypes from 'prop-types';

/**
 * 会话侧边栏:新会话按钮 + 会话列表 + fork/export 菜单 + 删除(R3-D1 拆分)。
 * 自 SmartChatPage.jsx L571-615 逐字搬运,状态与 handler 由 useSmartChat 注入。
 */
const SessionListPanel = ({
  sessions,
  currentSessionId,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
  onMenuClick,
}) => (
  <div className="session-list-panel">
    <button className="new-session-btn" onClick={onNewSession}>
      + 新会话
    </button>
    <ul className="session-list">
      {sessions.map(session => (
        <li
          key={session.id}
          className={`session-item ${currentSessionId === session.id ? 'active' : ''}`}
          onClick={() => onSwitchSession(session)}
        >
          <span className="session-title">{session.title}</span>
          <Dropdown
            menu={{
              items: [
                { key: 'fork', label: '创建副本' },
                { key: 'export', label: '导出 Markdown' },
              ],
              onClick: (info) => onMenuClick(session, info),
            }}
            trigger={['click']}
          >
            <button
              className="session-menu-btn"
              aria-label="会话操作"
              onClick={(e) => e.stopPropagation()}
            >
              ⋯
            </button>
          </Dropdown>
          <button
            className="delete-session-btn"
            onClick={(e) => {
              e.stopPropagation();
              onDeleteSession(session.id);
            }}
          >
            ×
          </button>
        </li>
      ))}
    </ul>
  </div>
);

SessionListPanel.propTypes = {
  sessions: PropTypes.array,
  currentSessionId: PropTypes.number,
  onNewSession: PropTypes.func.isRequired,
  onSwitchSession: PropTypes.func.isRequired,
  onDeleteSession: PropTypes.func.isRequired,
  onMenuClick: PropTypes.func.isRequired,
};

export default SessionListPanel;
