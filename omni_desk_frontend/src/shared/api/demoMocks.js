/**
 * Demo mode mock data for AI showcase features
 */

export const MOCK_DIFY_APPS = [
  {
    id: 1,
    name: '智能客服助手',
    description: '面向客户的 7×24 智能问答机器人，支持多轮对话与知识库检索',
    embed_url: 'https://udify.app/chatbot/gXvY6jZ9Q5kL3mN',
    is_active: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 2,
    name: '合同审查助手',
    description: '法务合同要点提取与风险标注，自动识别关键条款',
    embed_url: 'https://udify.app/chatbot/aB3cD5eF7gH9iJ',
    is_active: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 3,
    name: '员工手册问答',
    description: 'HR 政策智能检索，快速查询公司规章制度',
    embed_url: 'https://udify.app/chatbot/kL1mN3oP5qR7sT',
    is_active: false,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
];

export const MOCK_RAGFLOW_CONFIGS = [
  {
    id: 1,
    name: '企业知识库（演示）',
    api_endpoint: 'http://demo.ragflow.local',
    api_key: 'demo-key-masked',
    is_active: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 2,
    name: '产品文档库（演示）',
    api_endpoint: 'http://demo.ragflow.local',
    api_key: 'demo-key-masked',
    is_active: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
];

/**
 * 关键词 → 回答的映射表
 * 支持 10+ 条常见问题，未匹配时返回默认回答
 */
export const MOCK_RAGFLOW_RESPONSES = {
  '年假': '根据《员工手册》第 5.2 条：在公司连续工作满 1 年不满 10 年的，年休假 5 天；满 10 年不满 20 年的，年休假 10 天；满 20 年的，年休假 15 天。年假需提前 3 个工作日申请。',
  '报销': '差旅报销标准：\n- 交通：飞机经济舱、高铁二等座\n- 住宿：一线城市 500 元/晚，二线城市 400 元/晚\n- 伙食补助：100 元/天\n\n报销需在出差结束后 7 个工作日内提交，附上发票原件。',
  '加班': '加班需提前申请并经主管批准。加班补偿方式：\n- 工作日加班：1.5 倍工资或调休\n- 周末加班：2 倍工资或调休\n- 法定节假日：3 倍工资（不可调休）\n\n加班申请需在企业微信提交，并附上打卡记录。',
  '试用期': '试用期为 3 个月（特殊岗位可协商延长至 6 个月）。试用期工资为正式工资的 80%。试用期内享受正式员工同等福利（年假按实际工作月份折算）。',
  '转正': '转正流程：\n1. 试用期结束前 2 周，主管发起转正评估\n2. 员工填写转正自评表\n3. 主管填写评估意见\n4. HR 审核并通知结果\n\n转正后享受完整薪资福利。',
  '晋升': '公司每年 4 月和 10 月进行两次晋升窗口。晋升条件：\n- 在当前职级满 1 年以上\n- 最近两次绩效评估为 B 及以上\n- 无重大违纪记录\n\n晋升需提交申请并经晋升委员会评审。',
  '绩效': '绩效评估每季度进行一次（Q1/Q2/Q3/Q4），采用 OKR + 360 度评估。评级分为 S/A/B/C/D 五档：\n- S（卓越）：不超过 10%\n- A（优秀）：不超过 20%\n- B（良好）：约 50%\n- C（待改进）：约 15%\n- D（不合格）：不超过 5%',
  '社保': '公司按国家规定缴纳五险一金：\n- 养老保险：企业 16%，个人 8%\n- 医疗保险：企业 10%，个人 2%\n- 失业保险：企业 0.5%，个人 0.5%\n- 工伤保险：企业 0.4%，个人 0%\n- 生育保险：企业 0.8%，个人 0%\n- 住房公积金：企业 12%，个人 12%',
  '请假': '请假类型及额度：\n- 病假：每年累计不超过 3 个月\n- 事假：需提前申请，无薪\n- 婚假：法定 3 天，晚婚 10 天\n- 产假：女员工 158 天，男员工陪产假 15 天\n- 丧假：直系亲属 3 天\n\n请假需通过 OA 系统申请并附上相关证明。',
  '培训': '公司提供多种培训资源：\n- 内部培训：每月 1-2 次技术分享\n- 外部培训：可申请预算参加行业会议/课程\n- 在线学习：企业账号访问 Coursera/Udemy\n- 导师制度：新员工配备 1 对 1 导师\n\n培训费用报销需提前审批。',
  '__default__': '（演示模式）当前问题未在知识库中匹配到答案。生产环境将基于 RAGFlow 检索返回更精准的回答。您可以尝试其他关键词，或联系管理员补充知识库内容。',
};

/**
 * 根据问题内容匹配回答
 * @param {string} question - 用户问题
 * @returns {string} - 匹配的回答
 */
export function pickMockResponse(question) {
  if (!question || typeof question !== 'string') {
    return MOCK_RAGFLOW_RESPONSES['__default__'];
  }

  const lowerQuestion = question.toLowerCase();

  // 关键词匹配（按优先级排序）
  const keywords = Object.keys(MOCK_RAGFLOW_RESPONSES).filter(k => k !== '__default__');

  for (const keyword of keywords) {
    if (lowerQuestion.includes(keyword.toLowerCase())) {
      return MOCK_RAGFLOW_RESPONSES[keyword];
    }
  }

  return MOCK_RAGFLOW_RESPONSES['__default__'];
}
