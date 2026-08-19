import { Descriptions, Tag } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * announcement_query 公司公告卡片。
 * 由注册中心在 result.found && result.posts 时分发渲染。
 */
const AnnouncementQueryCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="公司公告" tagColor="geekblue" copyBtn={copyBtn}>
    {result.posts.map((post, idx) => (
      <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.posts.length - 1 ? 8 : 0 }}>
        <Descriptions.Item label="标题" span={2}>
          {post.title}
          {post.expires_at && <Tag color="orange" style={{ marginLeft: 8 }}>过期:{post.expires_at}</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="发布人">{post.author}</Descriptions.Item>
        <Descriptions.Item label="发布日期">{post.created_at}</Descriptions.Item>
        <Descriptions.Item label="内容" span={2}>{post.content}</Descriptions.Item>
      </Descriptions>
    ))}
  </ResultCardWrapper>
);

AnnouncementQueryCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    posts: PropTypes.arrayOf(PropTypes.shape({
      title: PropTypes.string,
      content: PropTypes.string,
      author: PropTypes.string,
      created_at: PropTypes.string,
      expires_at: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default AnnouncementQueryCard;
