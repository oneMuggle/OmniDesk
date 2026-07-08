import { Card, Descriptions, Tag, Badge } from 'antd';
import PropTypes from 'prop-types';
import AggregatedDayCard from './AggregatedDayCard';
import './ToolResult.css';

const ToolResult = ({ intent, result, sources }) => {
  if (!result) return null;

  if (intent === 'aggregated_day') {
    return <AggregatedDayCard {...result.data} />;
  }

  if (intent === 'schedule_query' && result.found) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="blue">排班信息</Tag>}>
          {result.schedules.map((schedule, idx) => (
            <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.schedules.length - 1 ? 8 : 0 }}>
              <Descriptions.Item label="日期">{schedule.duty_date}</Descriptions.Item>
              <Descriptions.Item label="值班人员">{schedule.duty_person}</Descriptions.Item>
              <Descriptions.Item label="值班领导">{schedule.duty_leader}</Descriptions.Item>
            </Descriptions>
          ))}
        </Card>
      </div>
    );
  }

  if (intent === 'personnel_query' && result.found) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="green">人员信息</Tag>}>
          {result.personnel.map((p, idx) => (
            <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.personnel.length - 1 ? 8 : 0 }}>
              <Descriptions.Item label="姓名">{p.name}</Descriptions.Item>
              <Descriptions.Item label="部门">{p.department}</Descriptions.Item>
              <Descriptions.Item label="职位">{p.position}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Badge status={p.status === '在职' ? 'success' : 'default'} text={p.status} />
              </Descriptions.Item>
              <Descriptions.Item label="电话">{p.phone_number}</Descriptions.Item>
            </Descriptions>
          ))}
        </Card>
      </div>
    );
  }

  if (intent === 'knowledge_qa' && sources && sources.length > 0) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="purple">引用来源</Tag>}>
          <ul className="sources-list">
            {sources.map((source, idx) => (
              <li key={idx}>
                {source.document}
                {source.score > 0 && <Tag style={{ marginLeft: 8 }}>相似度: {(source.score * 100).toFixed(0)}%</Tag>}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    );
  }

  if (intent === 'document_search' && result.found && result.documents) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="orange">文档搜索</Tag>}>
          {result.documents.map((doc, idx) => (
            <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.documents.length - 1 ? 8 : 0 }}>
              <Descriptions.Item label="类型">{doc.type}</Descriptions.Item>
              <Descriptions.Item label="标题">{doc.title}</Descriptions.Item>
              {doc.experiment_type && <Descriptions.Item label="实验类型">{doc.experiment_type}</Descriptions.Item>}
              {doc.client && <Descriptions.Item label="客户">{doc.client}</Descriptions.Item>}
              {doc.status && <Descriptions.Item label="状态">{doc.status}</Descriptions.Item>}
              {doc.owner && <Descriptions.Item label="创建人">{doc.owner}</Descriptions.Item>}
              {doc.start_date && <Descriptions.Item label="开始日期">{doc.start_date}</Descriptions.Item>}
              {doc.created_at && <Descriptions.Item label="创建时间">{doc.created_at}</Descriptions.Item>}
            </Descriptions>
          ))}
        </Card>
      </div>
    );
  }

  if (intent === 'event_query' && result.found) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="magenta">事件/日程</Tag>}>
          {result.schedules && result.schedules.length > 0 && (
            <Descriptions size="small" column={2} title="排班信息" style={{ marginBottom: 8 }}>
              <Descriptions.Item label="日期">{result.date}</Descriptions.Item>
              {result.schedules.map((s, idx) => (
                <>
                  <Descriptions.Item label="值班人员" key={`person-${idx}`}>{s.duty_person}</Descriptions.Item>
                  <Descriptions.Item label="值班领导" key={`leader-${idx}`}>{s.duty_leader}</Descriptions.Item>
                </>
              ))}
            </Descriptions>
          )}
          {result.holidays && result.holidays.length > 0 && (
            <Descriptions size="small" column={2} title="节假日">
              {result.holidays.map((h, idx) => (
                <>
                  <Descriptions.Item label="名称" key={`name-${idx}`}>{h.name}</Descriptions.Item>
                  <Descriptions.Item label="日期" key={`date-${idx}`}>{h.start_date} ~ {h.end_date}</Descriptions.Item>
                </>
              ))}
            </Descriptions>
          )}
        </Card>
      </div>
    );
  }

  if (intent === 'memo_query' && result.found && result.memos) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="cyan">备忘录</Tag>}>
          {result.memos.map((m, idx) => (
            <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.memos.length - 1 ? 8 : 0 }}>
              <Descriptions.Item label="标题">{m.title}</Descriptions.Item>
              <Descriptions.Item label="完成状态">
                <Badge status={m.is_completed ? 'success' : 'default'} text={m.is_completed ? '已完成' : '未完成'} />
              </Descriptions.Item>
              <Descriptions.Item label="内容" span={2}>{m.content}</Descriptions.Item>
              <Descriptions.Item label="创建人">{m.user}</Descriptions.Item>
              <Descriptions.Item label="创建日期">{m.created_at}</Descriptions.Item>
              {m.reminder_time !== '无提醒' && <Descriptions.Item label="提醒时间">{m.reminder_time}</Descriptions.Item>}
            </Descriptions>
          ))}
        </Card>
      </div>
    );
  }

  if (intent === 'project_status' && result.found && result.projects) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="volcano">项目信息</Tag>}>
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
        </Card>
      </div>
    );
  }

  if (intent === 'announcement_query' && result.found && result.posts) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="geekblue">公司公告</Tag>}>
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
        </Card>
      </div>
    );
  }

  if (intent === 'compliance_query' && result.found && result.issues) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="red">合规问题</Tag>}>
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
        </Card>
      </div>
    );
  }

  if (intent === 'external_link_query' && result.found && result.links) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="cyan">内网外链</Tag>}>
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
        </Card>
      </div>
    );
  }

  if (intent === 'news_search' && result.found && result.articles) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="gold">新闻/通知</Tag>}>
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
        </Card>
      </div>
    );
  }

  if (!result.found) {
    return (
      <div className="tool-result-card">
        <Tag color="default">{result.message || '未找到相关信息'}</Tag>
      </div>
    );
  }

  return null;
};

export default ToolResult;

ToolResult.propTypes = {
  intent: PropTypes.string,
  result: PropTypes.shape({
    found: PropTypes.bool,
    schedules: PropTypes.arrayOf(PropTypes.shape({
      duty_date: PropTypes.string,
      duty_person: PropTypes.string,
      duty_leader: PropTypes.string,
    })),
    personnel: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      department: PropTypes.string,
      position: PropTypes.string,
      status: PropTypes.string,
      phone_number: PropTypes.string,
    })),
    documents: PropTypes.arrayOf(PropTypes.shape({
      type: PropTypes.string,
      title: PropTypes.string,
      experiment_type: PropTypes.string,
      owner: PropTypes.string,
      client: PropTypes.string,
      status: PropTypes.string,
      start_date: PropTypes.string,
      created_at: PropTypes.string,
    })),
    holidays: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      start_date: PropTypes.string,
      end_date: PropTypes.string,
    })),
    memos: PropTypes.arrayOf(PropTypes.shape({
      title: PropTypes.string,
      content: PropTypes.string,
      user: PropTypes.string,
      is_completed: PropTypes.bool,
      reminder_time: PropTypes.string,
      created_at: PropTypes.string,
    })),
    projects: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      description: PropTypes.string,
      manager: PropTypes.string,
      status: PropTypes.string,
      start_date: PropTypes.string,
      end_date: PropTypes.string,
    })),
    articles: PropTypes.arrayOf(PropTypes.shape({
      title: PropTypes.string,
      link: PropTypes.string,
      publication_date: PropTypes.string,
      news_type: PropTypes.string,
      personnel: PropTypes.string,
    })),
    posts: PropTypes.arrayOf(PropTypes.shape({
      title: PropTypes.string,
      content: PropTypes.string,
      author: PropTypes.string,
      created_at: PropTypes.string,
      expires_at: PropTypes.string,
    })),
    issues: PropTypes.arrayOf(PropTypes.shape({
      issue_type: PropTypes.string,
      description: PropTypes.string,
      status: PropTypes.string,
      severity: PropTypes.string,
      project: PropTypes.string,
      due_date: PropTypes.string,
      location: PropTypes.string,
    })),
    links: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      url: PropTypes.string,
      category: PropTypes.string,
      description: PropTypes.string,
      sso_enabled: PropTypes.bool,
      sso_token_endpoint: PropTypes.string,
    })),
    message: PropTypes.string,
  }),
  sources: PropTypes.arrayOf(PropTypes.shape({
    document: PropTypes.string,
    score: PropTypes.number,
  })),
};
