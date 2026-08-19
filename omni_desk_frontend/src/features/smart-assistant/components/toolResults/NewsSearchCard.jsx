import { Descriptions } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * news_search 新闻/通知卡片 — 有链接时渲染 <a>。
 * 由注册中心在 result.found && result.articles 时分发渲染。
 */
const NewsSearchCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="新闻/通知" tagColor="gold" copyBtn={copyBtn}>
    {result.articles.map((a, idx) => (
      <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.articles.length - 1 ? 8 : 0 }}>
        <Descriptions.Item label="标题">
          {a.link ? <a href={a.link} target="_blank" rel="noopener noreferrer">{a.title}</a> : a.title}
        </Descriptions.Item>
        <Descriptions.Item label="类型">{a.news_type}</Descriptions.Item>
        <Descriptions.Item label="发布日期">{a.publication_date}</Descriptions.Item>
        <Descriptions.Item label="发布人">{a.personnel}</Descriptions.Item>
      </Descriptions>
    ))}
  </ResultCardWrapper>
);

NewsSearchCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    articles: PropTypes.arrayOf(PropTypes.shape({
      title: PropTypes.string,
      link: PropTypes.string,
      publication_date: PropTypes.string,
      news_type: PropTypes.string,
      personnel: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default NewsSearchCard;
