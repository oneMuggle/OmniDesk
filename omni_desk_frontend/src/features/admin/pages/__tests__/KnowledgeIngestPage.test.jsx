/**
 * S4-2:控制台「AI 管理 → 知识入库」。
 */
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import KnowledgeIngestPage from '../KnowledgeIngestPage';

jest.mock('../../../smart-assistant/api/smartAssistantApi', () => ({
  getKnowledgeIngestSummary: jest.fn(),
  reconcileKnowledgeSources: jest.fn(),
  retryKnowledgeSource: jest.fn(),
}));

const api = () => require('../../../smart-assistant/api/smartAssistantApi');

const SUMMARY = {
  enabled: true,
  dataset_configured: true,
  source_types: [
    { value: 'announcement', label: '公告' },
    { value: 'paperless_document', label: '文档库' },
  ],
  statuses: [
    { value: 'pending', label: '待入库' },
    { value: 'ingested', label: '已入库' },
    { value: 'failed', label: '失败' },
    { value: 'removed', label: '已移除' },
  ],
  counts: {
    announcement: { pending: 0, ingested: 12, failed: 0, removed: 1 },
    paperless_document: { pending: 2, ingested: 30, failed: 1, removed: 0 },
  },
  failures: [
    {
      id: 9,
      source_type: 'paperless_document',
      source_type_display: '文档库',
      source_id: 4,
      title: '采购合同',
      status: 'failed',
      attempts: 5,
      last_error: 'RagflowClientError: timeout',
      updated_at: '2026-09-28T02:00:00Z',
    },
  ],
};

const rowOf = (text) => screen.getAllByRole('row').find((row) => within(row).queryByText(text));

beforeEach(() => {
  jest.clearAllMocks();
  api().getKnowledgeIngestSummary.mockResolvedValue({ data: SUMMARY });
  api().reconcileKnowledgeSources.mockResolvedValue({ data: { queued: true } });
  api().retryKnowledgeSource.mockResolvedValue({ data: {} });
});

describe('KnowledgeIngestPage', () => {
  it('显示各来源各状态数量与失败记录', async () => {
    render(<KnowledgeIngestPage />);
    expect(await screen.findByText('采购合同')).toBeInTheDocument();
    const docRow = rowOf('文档库');
    expect(within(docRow).getByText('30')).toBeInTheDocument();
    expect(within(rowOf('公告')).getByText('12')).toBeInTheDocument();
    const failRow = rowOf('采购合同');
    expect(within(failRow).getByText('RagflowClientError: timeout')).toBeInTheDocument();
    expect(within(failRow).getByText('5')).toBeInTheDocument();
    expect(screen.queryByText('自动入库未启用')).not.toBeInTheDocument();
  });

  it('重试一条失败记录', async () => {
    render(<KnowledgeIngestPage />);
    await screen.findByText('采购合同');
    fireEvent.click(within(rowOf('采购合同')).getByRole('button', { name: /重\s*试/ }));
    await waitFor(() => expect(api().retryKnowledgeSource).toHaveBeenCalledWith(9));
  });

  it('立即对账', async () => {
    render(<KnowledgeIngestPage />);
    await screen.findByText('采购合同');
    fireEvent.click(screen.getByRole('button', { name: /立即对账/ }));
    await waitFor(() => expect(api().reconcileKnowledgeSources).toHaveBeenCalledTimes(1));
  });

  it('未配置时提示并禁用对账', async () => {
    api().getKnowledgeIngestSummary.mockResolvedValue({
      data: { ...SUMMARY, enabled: false, dataset_configured: false, failures: [] },
    });
    render(<KnowledgeIngestPage />);
    expect(await screen.findByText('自动入库未启用')).toBeInTheDocument();
    expect(screen.getByText(/SMART_ASSISTANT_INGEST_DATASET_ID/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /立即对账/ })).toBeDisabled();
    expect(screen.getByText('没有失败记录')).toBeInTheDocument();
  });

  it('加载失败不崩溃', async () => {
    api().getKnowledgeIngestSummary.mockRejectedValue(new Error('boom'));
    render(<KnowledgeIngestPage />);
    await waitFor(() => expect(api().getKnowledgeIngestSummary).toHaveBeenCalled());
    expect(screen.getByText('没有失败记录')).toBeInTheDocument();
  });
});
