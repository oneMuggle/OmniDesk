import { Link } from 'react-router-dom';
import { Card, Col, Row, Typography } from 'antd';
import { ASSISTANT_APPS, appPath } from './assistantNav';

/**
 * 智能助手「应用」标签(S2-2):原独立的 Dify / Ragflow / Office / 文件分析页面的入口。
 */
const AssistantAppsPage = () => (
  <div className="assistant-apps-page">
    <Typography.Paragraph type="secondary">
      日常问答请直接在「对话」中提问；下面是需要专门界面的 AI 应用。
    </Typography.Paragraph>
    <Row gutter={[16, 16]}>
      {ASSISTANT_APPS.map((app) => (
        <Col key={app.key} xs={24} sm={12} lg={6}>
          <Link to={appPath(app.key)} aria-label={app.title}>
            <Card hoverable className="assistant-app-card" title={app.title}>
              <Typography.Text type="secondary">{app.description}</Typography.Text>
            </Card>
          </Link>
        </Col>
      ))}
    </Row>
  </div>
);

export default AssistantAppsPage;
