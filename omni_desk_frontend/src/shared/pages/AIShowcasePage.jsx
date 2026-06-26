import { Card, Button, Row, Col, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { RobotOutlined, ExperimentOutlined } from '@ant-design/icons';
import './AIShowcasePage.css';

const { Title, Paragraph } = Typography;

const AIShowcasePage = () => {
  const navigate = useNavigate();

  return (
    <div className="ai-showcase-page">
      <div className="showcase-header">
        <Title level={2}>AI 能力展示</Title>
        <Paragraph>
          OmniDesk 集成了 Dify 和 RAGFlow 两大 AI 平台，为企业提供智能问答、知识库检索等能力。
        </Paragraph>
      </div>

      <Row gutter={[24, 24]} justify="center">
        <Col xs={24} md={12} lg={10}>
          <Card
            className="showcase-card"
            hoverable
            cover={
              <div className="card-icon dify">
                <RobotOutlined style={{ fontSize: 64, color: '#1890ff' }} />
              </div>
            }
          >
            <Card.Meta
              title="Dify 智能应用"
              description="快速构建 AI 应用，支持多轮对话、知识库集成、工作流编排"
            />
            <div className="card-features">
              <ul>
                <li>智能客服助手</li>
                <li>合同审查工具</li>
                <li>员工手册问答</li>
              </ul>
            </div>
            <Button
              type="primary"
              block
              onClick={() => navigate('/dify-apps')}
              style={{ marginTop: 16 }}
            >
              立即体验 →
            </Button>
          </Card>
        </Col>

        <Col xs={24} md={12} lg={10}>
          <Card
            className="showcase-card"
            hoverable
            cover={
              <div className="card-icon ragflow">
                <ExperimentOutlined style={{ fontSize: 64, color: '#52c41a' }} />
              </div>
            }
          >
            <Card.Meta
              title="RAGFlow 知识检索"
              description="基于 RAG 的企业知识库问答，精准检索与智能回答"
            />
            <div className="card-features">
              <ul>
                <li>企业知识库问答</li>
                <li>产品文档检索</li>
                <li>多轮对话支持</li>
              </ul>
            </div>
            <Button
              type="primary"
              block
              onClick={() => navigate('/ragflow-chat')}
              style={{ marginTop: 16 }}
            >
              立即体验 →
            </Button>
          </Card>
        </Col>
      </Row>

      <div className="showcase-footer">
        <Paragraph type="secondary">
          💡 提示：开启右上角"演示模式"可在无后端服务时体验完整流程
        </Paragraph>
      </div>
    </div>
  );
};

export default AIShowcasePage;
