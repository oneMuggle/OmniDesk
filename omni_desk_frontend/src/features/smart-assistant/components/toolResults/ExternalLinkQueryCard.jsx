import { Descriptions, Tag } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * external_link_query 内网外链卡片 — SSO 启用时优先渲染 sso_token_endpoint。
 * 由注册中心在 result.found && result.links 时分发渲染。
 */
const ExternalLinkQueryCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="内网外链" tagColor="cyan" copyBtn={copyBtn}>
    {result.links.map((link, idx) => (
      <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.links.length - 1 ? 8 : 0 }}>
        <Descriptions.Item label="名称" span={2}>
          {link.sso_enabled && link.sso_token_endpoint ? (
            <a href={link.sso_token_endpoint} target="_blank" rel="noopener noreferrer">{link.name}</a>
          ) : (
            <a href={link.url} target="_blank" rel="noopener noreferrer">{link.name}</a>
          )}
          {link.sso_enabled && <Tag color="purple" style={{ marginLeft: 8 }}>SSO</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="分类">{link.category}</Descriptions.Item>
        <Descriptions.Item label="地址">
          {link.sso_enabled && link.sso_token_endpoint ? link.sso_token_endpoint : link.url}
        </Descriptions.Item>
        {link.description && <Descriptions.Item label="说明" span={2}>{link.description}</Descriptions.Item>}
      </Descriptions>
    ))}
  </ResultCardWrapper>
);

ExternalLinkQueryCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    links: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      url: PropTypes.string,
      category: PropTypes.string,
      description: PropTypes.string,
      sso_enabled: PropTypes.bool,
      sso_token_endpoint: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default ExternalLinkQueryCard;
