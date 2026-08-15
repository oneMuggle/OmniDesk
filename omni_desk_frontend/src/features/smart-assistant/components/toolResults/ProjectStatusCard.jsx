import { Descriptions, Badge } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * project_status 项目信息卡片。
 * 由注册中心在 result.found && result.projects 时分发渲染。
 */
const ProjectStatusCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="项目信息" tagColor="volcano" copyBtn={copyBtn}>
    {result.projects.map((p, idx) => (
      <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.projects.length - 1 ? 8 : 0 }}>
        <Descriptions.Item label="项目名称">{p.name}</Descriptions.Item>
        <Descriptions.Item label="负责人">{p.manager}</Descriptions.Item>
        <Descriptions.Item label="状态">
          <Badge status={p.status === '进行中' ? 'processing' : p.status === '已完成' ? 'success' : 'default'} text={p.status} />
        </Descriptions.Item>
        <Descriptions.Item label="描述">{p.description}</Descriptions.Item>
        <Descriptions.Item label="开始日期">{p.start_date}</Descriptions.Item>
        <Descriptions.Item label="结束日期">{p.end_date}</Descriptions.Item>
      </Descriptions>
    ))}
  </ResultCardWrapper>
);

ProjectStatusCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    projects: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      description: PropTypes.string,
      manager: PropTypes.string,
      status: PropTypes.string,
      start_date: PropTypes.string,
      end_date: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default ProjectStatusCard;
