import AggregatedDayResultCard from './AggregatedDayResultCard';
import ScheduleResultCard from './ScheduleResultCard';
import PersonnelResultCard from './PersonnelResultCard';
import KnowledgeQaCard from './KnowledgeQaCard';
import DocumentSearchCard from './DocumentSearchCard';
import EventQueryCard from './EventQueryCard';
import MemoQueryCard from './MemoQueryCard';
import ProjectStatusCard from './ProjectStatusCard';
import AnnouncementQueryCard from './AnnouncementQueryCard';
import ComplianceQueryCard from './ComplianceQueryCard';
import ExternalLinkQueryCard from './ExternalLinkQueryCard';
import NewsSearchCard from './NewsSearchCard';

/**
 * 注册中心: intent → { component, when }。
 *
 * when 为分发守卫,精确镜像重构前 ToolResult 的顺序 if 链分支条件;
 * 守卫不通过时由 ToolResult 薄壳自然落回兜底链(!found → file_download → null),
 * 与现行短路行为等价。
 */
const TOOL_RESULT_REGISTRY = {
  aggregated_day: {
    component: AggregatedDayResultCard,
    when: () => true,
  },
  schedule_query: {
    component: ScheduleResultCard,
    when: (result) => Boolean(result && result.found),
  },
  personnel_query: {
    component: PersonnelResultCard,
    when: (result) => Boolean(result && result.found),
  },
  knowledge_qa: {
    component: KnowledgeQaCard,
    when: (result, sources) => Array.isArray(sources) && sources.length > 0,
  },
  document_search: {
    component: DocumentSearchCard,
    when: (result) => Boolean(result && result.found && result.documents),
  },
  event_query: {
    component: EventQueryCard,
    when: (result) => Boolean(result && result.found),
  },
  memo_query: {
    component: MemoQueryCard,
    when: (result) => Boolean(result && result.found && result.memos),
  },
  project_status: {
    component: ProjectStatusCard,
    when: (result) => Boolean(result && result.found && result.projects),
  },
  announcement_query: {
    component: AnnouncementQueryCard,
    when: (result) => Boolean(result && result.found && result.posts),
  },
  compliance_query: {
    component: ComplianceQueryCard,
    when: (result) => Boolean(result && result.found && result.issues),
  },
  external_link_query: {
    component: ExternalLinkQueryCard,
    when: (result) => Boolean(result && result.found && result.links),
  },
  news_search: {
    component: NewsSearchCard,
    when: (result) => Boolean(result && result.found && result.articles),
  },
};

export default TOOL_RESULT_REGISTRY;
