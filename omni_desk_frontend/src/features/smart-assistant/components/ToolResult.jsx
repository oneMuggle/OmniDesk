import { useState } from 'react';
import { Card, Tag, Button } from 'antd';
import { CopyOutlined, CheckOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import TOOL_RESULT_REGISTRY from './toolResults/registry';
import FileDownloadCard from './toolResults/FileDownloadCard';
import serializeResult from '../utils/serializeResult';
import './ToolResult.css';

/**
 * ToolResult — 工具结果渲染薄壳。
 * 按 intent 经注册中心分发到对应卡片组件;未命中时落回兜底链:
 * !found → 未找到 Tag / file_download → 下载卡片 / 否则 null。
 */
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

  const entry = TOOL_RESULT_REGISTRY[intent];
  if (entry && entry.when(result, sources)) {
    const CardComponent = entry.component;
    return <CardComponent result={result} sources={sources} copyBtn={copyBtn} />;
  }

  if (!result.found) {
    return (
      <div className="tool-result-card">
        <Tag color="default">{result.message || '未找到相关信息'}</Tag>
        {copyBtn}
      </div>
    );
  }

  // 未知 intent 但 result.found=true,尝试渲染 file_download(若存在)
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

  // 安全 DTO 仅保留摘要/计数时，仍展示可用信息，避免 200 响应静默降级为空卡片。
  if (result.summary || result.count !== undefined || result.total !== undefined) {
    return (
      <div className="tool-result-card">
        <Card size="small" title="查询结果">
          {result.summary && <div>{result.summary}</div>}
          {(result.count !== undefined || result.total !== undefined) && (
            <div>共 {result.count ?? result.total} 条</div>
          )}
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
    file_download: PropTypes.shape({
      filename: PropTypes.string,
      download_url: PropTypes.string,
    }),
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
