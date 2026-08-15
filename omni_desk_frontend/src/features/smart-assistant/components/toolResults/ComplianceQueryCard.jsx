import { Descriptions, Tag } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * compliance_query 合规问题卡片 — severity/status 双 Tag 渲染。
 * 由注册中心在 result.found && result.issues 时分发渲染。
 */
const ComplianceQueryCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="合规问题" tagColor="red" copyBtn={copyBtn}>
    {result.issues.map((issue, idx) => (
      <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.issues.length - 1 ? 8 : 0 }}>
        <Descriptions.Item label="问题类型" span={2}>
          {issue.issue_type}
          {issue.severity && (
            <Tag
              color={issue.severity === '紧急' ? 'red' : issue.severity === '高' ? 'volcano' : issue.severity === '中' ? 'orange' : 'default'}
              style={{ marginLeft: 8 }}
            >
              {issue.severity}
            </Tag>
          )}
          {issue.status && (
            <Tag color={issue.status === '已解决' ? 'green' : 'blue'} style={{ marginLeft: 4 }}>
              {issue.status}
            </Tag>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="所属项目">{issue.project}</Descriptions.Item>
        <Descriptions.Item label="截止日期">{issue.due_date || '无'}</Descriptions.Item>
        {issue.location && <Descriptions.Item label="问题位置" span={2}>{issue.location}</Descriptions.Item>}
        <Descriptions.Item label="描述" span={2}>{issue.description}</Descriptions.Item>
      </Descriptions>
    ))}
  </ResultCardWrapper>
);

ComplianceQueryCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    issues: PropTypes.arrayOf(PropTypes.shape({
      issue_type: PropTypes.string,
      description: PropTypes.string,
      status: PropTypes.string,
      severity: PropTypes.string,
      project: PropTypes.string,
      due_date: PropTypes.string,
      location: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default ComplianceQueryCard;
