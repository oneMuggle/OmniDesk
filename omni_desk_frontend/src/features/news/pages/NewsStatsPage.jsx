import { useEffect, useState } from 'react';
import { getNewsStats, getNewsArticles } from '../api/newsApi';
import { Table, Typography, Card, Row, Col } from 'antd';
import { logger } from '../../../shared/utils/logger';

const { Title, Text } = Typography;

const NewsStatsPage = () => {
  const [stats, setStats] = useState({});
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const statsRes = await getNewsStats();
        setStats(statsRes.data);
        const articlesRes = await getNewsArticles();
        setArticles(articlesRes.data.results || []);
      } catch (error) {
        logger.error('Failed to fetch news data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: '链接',
      dataIndex: 'link',
      key: 'link',
      render: (link) => <a href={link} target="_blank" rel="noopener noreferrer">{link}</a>,
    },
    {
        title: '发布日期',
        dataIndex: 'publication_date',
        key: 'publication_date',
    },
    {
        title: '关联人员',
        dataIndex: ['personnel', 'name'],
        key: 'personnel',
    },
    {
        title: '新闻类型',
        dataIndex: ['news_type', 'name'],
        key: 'news_type',
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <Title level={2}>新闻统计</Title>
      {loading ? (
        <p>加载中...</p>
      ) : (
        stats && (
          <>
            <Row gutter={16} style={{ marginBottom: '20px' }}>
              <Col span={8}>
                <Card>
                  <Title level={4}>总文章数</Title>
                  <Text>{stats.total_articles}</Text>
                </Card>
              </Col>
            </Row>
            <Title level={3}>新闻发布情况</Title>
            {Object.entries(stats.by_person).map(([person, personData]) => (
              <Card key={person} title={person} style={{ marginBottom: '16px' }}>
                <p><strong>总计: {personData.total}篇</strong></p>
                {Object.entries(personData.monthly).map(([month, count]) => (
                  <p key={month}>{`${month}: ${count}篇`}</p>
                ))}
              </Card>
            ))}
          </>
        )
      )}
      <Title level={3} style={{ marginTop: '20px' }}>新闻列表</Title>
      <Table
        columns={columns}
        dataSource={articles}
        rowKey="id"
        loading={loading}
      />
    </div>
  );
};

export default NewsStatsPage;