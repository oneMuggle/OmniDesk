import normalizeAggregatedResult from './normalizeAggregatedResult';

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

export default serializeResult;
