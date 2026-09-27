import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Tabs } from 'antd';
import { ASSISTANT_TABS, activeAssistantTab } from './assistantNav';
import './SmartAssistantLayout.css';

/**
 * 智能助手统一入口(S2-2):顶部「对话 / 任务 / 应用」标签 + 内容区。
 * 原「多 Agent 任务」「Dify / Ragflow / Office / 文件分析」独立页面挂在这里,旧地址重定向过来。
 */
const SmartAssistantLayout = () => {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const activeKey = activeAssistantTab(pathname);

  const handleChange = (key) => {
    const tab = ASSISTANT_TABS.find((item) => item.key === key);
    if (tab) navigate(tab.to);
  };

  return (
    <div className="smart-assistant-layout" data-testid="smart-assistant-layout">
      <nav className="smart-assistant-layout-nav" aria-label="智能助手导航">
        <Tabs
          activeKey={activeKey}
          onChange={handleChange}
          items={ASSISTANT_TABS.map(({ key, label }) => ({ key, label }))}
        />
      </nav>
      <div className="smart-assistant-layout-content">
        <Outlet />
      </div>
    </div>
  );
};

export default SmartAssistantLayout;
