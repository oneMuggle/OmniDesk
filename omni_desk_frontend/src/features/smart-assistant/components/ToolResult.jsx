import React, { useState } from 'react';
import { Card, Descriptions, Tag, Badge, Button, Space, message } from 'antd';
import { CopyOutlined, CheckOutlined, DownloadOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import AggregatedDayCard from './AggregatedDayCard';
import { downloadOfficeFile } from '../api/smartAssistantApi';
import './ToolResult.css';

/**
 * Office 文件下载卡片 — 后端 office_generate 工具会返回
 * tool_result.file_download = { filename, download_url }。
 * download_url 末段是 token,点击下载按钮 → 调 downloadOfficeFile(token)
 * 拿 blob → createObjectURL 触发浏览器下载。
 */
function FileDownloadCard({ fileDownload }) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    try {
      const token = (fileDownload.download_url || '').split('/').filter(Boolean).pop();
      const blob = await downloadOfficeFile(token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileDownload.filename || 'document.docx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      message.error(err.message || '下载失败');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Card size="small" style={{ marginTop: 8 }}>
      <Space>
        <span>{fileDownload.filename}</span>
        <Button icon={<DownloadOutlined />} size="small" onClick={handleDownload} loading={downloading}>
          下载
        </Button>
      </Space>
    </Card>
  );
}

FileDownloadCard.propTypes = {
  fileDownload: PropTypes.shape({
    filename: PropTypes.string,
    download_url: PropTypes.string,
  }).isRequired,
};

/**
 * 规范化聚合查询(aggregated_day)结果。
 * 后端 ResultSynthesizer 返回扁平结构 {summary, items, total_count, moduleCounts, chain_results};
 * 同时兼容未来可能出现的 {data: {...}} 包层结构。
 */
const normalizeAggregatedResult = (result) => {
  if (!result || typeof result !== 'object') return {};
  const wrapped = result.data;
  if (
    wrapped &&
    typeof wrapped === 'object' &&
    (wrapped.items || wrapped.moduleCounts || wrapped.summary)
  ) {
    return wrapped;
  }
  return result;
};

/**
 * 将工具结果序列化为可复制的纯文本。
 * 不同 intent 使用不同的格式化策略。
 */
const serializeResult = (intent, result, sources) => {
  if (!result) return '';

  if (intent === 'schedule_query' && result.found && result.schedules) {
    return result.schedules.map(s =>
      `日期: ${s.duty_date}\n值班人员: ${s.duty_person}\n值班领导: ${s.duty_leader}`
    ).join('\n---\n');
  }

  if (intent === 'personnel_query' && result.found && result.personnel) {
    return result.personnel.map(p =>
      `姓名: ${p.name}\n部门: ${p.department}\n职位: ${p.position}\n状态: ${p.status}\n电话: ${p.phone_number}`
    ).join('\n---\n');
  }

  if (intent === 'knowledge_qa' && sources && sources.length > 0) {
    return sources.map(s =>
      `${s.document}${s.score > 0 ? ` (相似度: ${(s.score * 100).toFixed(0)}%)` : ''}`
    ).join('\n');
  }

  if (intent === 'document_search' && result.found && result.documents) {
    return result.documents.map(d =>
      `标题: ${d.title}\n类型: ${d.type}${d.owner ? `\n创建人: ${d.owner}` : ''}${d.start_date ? `\n开始日期: ${d.start_date}` : ''}`
    ).join('\n---\n');
  }

  if (intent === 'event_query' && result.found) {
    const parts = [];
    if (result.schedules) {
      parts.push(result.schedules.map(s =>
        `日期: ${result.date}\n值班人员: ${s.duty_person}\n值班领导: ${s.duty_leader}`
      ).join('\n'));
    }
    if (result.holidays) {
      parts.push(result.holidays.map(h =>
        `节假日: ${h.name}\n日期: ${h.start_date} ~ ${h.end_date}`
      ).join('\n'));
    }
    return parts.join('\n---\n');
  }

  if (intent === 'memo_query' && result.found && result.memos) {
    return result.memos.map(m =>
      `标题: ${m.title}\n状态: ${m.is_completed ? '已完成' : '未完成'}\n内容: ${m.content}\n创建人: ${m.user}\n创建日期: ${m.created_at}`
    ).join('\n---\n');
  }

  if (intent === 'project_status' && result.found && result.projects) {
    return result.projects.map(p =>
      `项目: ${p.name}\n负责人: ${p.manager}\n状态: ${p.status}\n描述: ${p.description}\n开始: ${p.start_date}\n结束: ${p.end_date}`
    ).join('\n---\n');
  }

  if (intent === 'announcement_query' && result.found && result.posts) {
    return result.posts.map(p =>
      `标题: ${p.title}\n发布人: ${p.author}\n日期: ${p.created_at}\n内容: ${p.content}`
    ).join('\n---\n');
  }

  if (intent === 'compliance_query' && result.found && result.issues) {
    return result.issues.map(issue =>
      `类型: ${issue.issue_type}${issue.severity ? `\n严重度: ${issue.severity}` : ''}\n项目: ${issue.project}\n描述: ${issue.description}`
    ).join('\n---\n');
  }

  if (intent === 'external_link_query' && result.found && result.links) {
    return result.links.map(l =>
      `名称: ${l.name}\n分类: ${l.category}\n地址: ${l.sso_enabled && l.sso_token_endpoint ? l.sso_token_endpoint : l.url}`
    ).join('\n---\n');
  }

  if (intent === 'news_search' && result.found && result.articles) {
    return result.articles.map(a =>
      `标题: ${a.title}\n类型: ${a.news_type}\n发布日期: ${a.publication_date}${a.personnel ? `\n发布人: ${a.personnel}` : ''}${a.link ? `\n链接: ${a.link}` : ''}`
    ).join('\n---\n');
  }

  if (intent === 'aggregated_day') {
    const data = normalizeAggregatedResult(result);
    try {
      return JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  }

  if (!result.found) {
    return result.message || '未找到相关信息';
  }

  // 兜底:JSON 序列化
  try {
    return JSON.stringify(result, null, 2);
  } catch {
    return String(result);
  }
};

/**
 * 通用结果卡片包装器 — 消除重复的 wrapper 结构。
 * 所有 intent 分支共享: div.tool-result-card > Card + 复制按钮
 */
const ResultCardWrapper = ({ title, tagColor, children, copyBtn }) => (
  <div className="tool-result-card">
    <Card size="small" title={<Tag color={tagColor}>{title}</Tag>}>
      {children}
    </Card>
    {copyBtn}
  </div>
);

ResultCardWrapper.propTypes = {
  title: PropTypes.string.isRequired,
  tagColor: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
  copyBtn: PropTypes.node.isRequired,
};

const ToolResult = ({ intent, result, sources }) => {
  const [copied, setCopied] = useState(false);

  if (!result) return null;

  const handleCopy = () => {
    const text = serializeResult(intent, result, sources);
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      // 静默失败
    });
  };

  const copyBtn = (
    <Button
      type="text"
      size="small"
      icon={copied
        ? <CheckOutlined style={{ color: '#52c41a' }} />
        : <CopyOutlined />}
      onClick={handleCopy}
      className="tool-copy-btn"
      title="复制结果"
    />
  );

  if (intent === 'aggregated_day') {
    const aggData = normalizeAggregatedResult(result);
    return (
      <div className="tool-result-card">
        <AggregatedDayCard
          items={aggData.items}
          moduleCounts={aggData.moduleCounts}
          summary={aggData.summary}
        />
        {copyBtn}
      </div>
    );
  }

  if (intent === 'schedule_query' && result.found) {
    return (
      <ResultCardWrapper title="排班信息" tagColor="blue" copyBtn={copyBtn}>
        {result.schedules.map((schedule, idx) => (
          <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.schedules.length - 1 ? 8 : 0 }}>
            <Descriptions.Item label="日期">{schedule.duty_date}</Descriptions.Item>
            <Descriptions.Item label="值班人员">{schedule.duty_person}</Descriptions.Item>
            <Descriptions.Item label="值班领导">{schedule.duty_leader}</Descriptions.Item>
          </Descriptions>
        ))}
      </ResultCardWrapper>
    );
  }

  if (intent === 'personnel_query' && result.found) {
    return (
      <ResultCardWrapper title="人员信息" tagColor="green" copyBtn={copyBtn}>
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
      </ResultCardWrapper>
    );
  }

  if (intent === 'knowledge_qa' && sources && sources.length > 0) {
    return (
      <ResultCardWrapper title="引用来源" tagColor="purple" copyBtn={copyBtn}>
        <ul className="sources-list">
          {sources.map((source, idx) => (
            <li key={idx}>
              {source.document}
              {source.score > 0 && <Tag style={{ marginLeft: 8 }}>相似度: {(source.score * 100).toFixed(0)}%</Tag>}
            </li>
          ))}
        </ul>
      </ResultCardWrapper>
    );
  }

  if (intent === 'document_search' && result.found && result.documents) {
    return (
      <ResultCardWrapper title="文档搜索" tagColor="orange" copyBtn={copyBtn}>
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
      </ResultCardWrapper>
    );
  }

  if (intent === 'event_query' && result.found) {
    return (
      <ResultCardWrapper title="事件/日程" tagColor="magenta" copyBtn={copyBtn}>
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
      </ResultCardWrapper>
    );
  }

  if (intent === 'memo_query' && result.found && result.memos) {
    return (
      <ResultCardWrapper title="备忘录" tagColor="cyan" copyBtn={copyBtn}>
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
      </ResultCardWrapper>
    );
  }

  if (intent === 'project_status' && result.found && result.projects) {
    return (
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
  }

  if (intent === 'announcement_query' && result.found && result.posts) {
    return (
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
  }

  if (intent === 'compliance_query' && result.found && result.issues) {
    return (
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
  }

  if (intent === 'external_link_query' && result.found && result.links) {
    return (
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
  }

  if (intent === 'news_search' && result.found && result.articles) {
    return (
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
  }

  if (!result.found) {
    return (
      <div className="tool-result-card">
        <Tag color="default">{result.message || '未找到相关信息'}</Tag>
        {copyBtn}
      </div>
    );
  }

  // 兜底:未知 intent 但 result.found=true,尝试渲染 file_download(若存在)
  // 与 intent-specific 分支独立,确保 office_generate 等工具的下载卡片一定能呈现
  if (result.file_download) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="cyan">生成文件</Tag>}>
          <FileDownloadCard fileDownload={result.file_download} />
        </Card>
        {copyBtn}
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
    date: PropTypes.string,
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
    // aggregated_day 扁平结构(后端 ResultSynthesizer 输出)
    summary: PropTypes.string,
    items: PropTypes.arrayOf(PropTypes.shape({
      type: PropTypes.string,
      module: PropTypes.string,
      data: PropTypes.object,
      sort_key: PropTypes.string,
    })),
    total_count: PropTypes.number,
    moduleCounts: PropTypes.object,
    chain_results: PropTypes.array,
    // 兼容未来可能的包层结构
    data: PropTypes.object,
  }),
  sources: PropTypes.arrayOf(PropTypes.shape({
    document: PropTypes.string,
    score: PropTypes.number,
  })),
};
