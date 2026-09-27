import { useEffect, useState } from 'react';
import { Button, Card, Space, Typography } from 'antd';
import { RobotOutlined } from '@ant-design/icons';
import { getAssistantContext } from '../../../features/smart-assistant/api/smartAssistantApi';
import { openAIDrawer } from '../../utils/aiDrawer';

const DASHBOARD_ROUTE = '/';

/**
 * Dashboard AI 卡片(S2):展示首页快捷问题,点击后打开 AI 抽屉并直接提问。
 *
 * 快捷问题由各模块 ai_tools.py 用 QuickPrompt(routes=(r"^/$",)) 声明,后端按
 * 当前用户能调用的工具过滤;接口失败或列表为空时不渲染卡片。
 */
const AssistantCard = () => {
  const [prompts, setPrompts] = useState([]);

  useEffect(() => {
    let cancelled = false;
    getAssistantContext(DASHBOARD_ROUTE)
      .then((resp) => {
        const list = resp?.data?.quick_prompts;
        if (!cancelled) setPrompts(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (!cancelled) setPrompts([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (prompts.length === 0) return null;

  return (
    <Card
      className="dashboard-assistant-card"
      data-testid="dashboard-assistant-card"
      style={{ marginBottom: 24 }}
      title={(
        <Space>
          <RobotOutlined />
          <span>问问智能助手</span>
        </Space>
      )}
      extra={<Button type="link" onClick={() => openAIDrawer()}>打开助手</Button>}
    >
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        助手会按你的权限跨模块查询,点一下就能问:
      </Typography.Paragraph>
      <Space wrap>
        {prompts.map((prompt) => (
          <Button key={prompt.query} shape="round" title={prompt.query} onClick={() => openAIDrawer({ query: prompt.query })}>
            {prompt.label}
          </Button>
        ))}
      </Space>
    </Card>
  );
};

export default AssistantCard;
