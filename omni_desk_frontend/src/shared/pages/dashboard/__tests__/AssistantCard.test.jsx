import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AssistantCard from '../AssistantCard';
import { AI_DRAWER_EVENT } from '../../../utils/aiDrawer';

jest.mock('../../../../features/smart-assistant/api/smartAssistantApi', () => ({
  getAssistantContext: jest.fn(),
}));

const api = () => require('../../../../features/smart-assistant/api/smartAssistantApi');

describe('Dashboard AssistantCard', () => {
  let received;
  const listener = (event) => received.push(event.detail);

  beforeEach(() => {
    jest.clearAllMocks();
    received = [];
    window.addEventListener(AI_DRAWER_EVENT, listener);
  });

  afterEach(() => {
    window.removeEventListener(AI_DRAWER_EVENT, listener);
  });

  it('拉取首页快捷问题并渲染,点击后唤起抽屉提问', async () => {
    api().getAssistantContext.mockResolvedValue({
      data: { quick_prompts: [{ label: '今天安排', query: '我今天有什么安排？', toolset: 'schedule' }] },
    });
    render(<AssistantCard />);

    fireEvent.click(await screen.findByRole('button', { name: '今天安排' }));
    expect(api().getAssistantContext).toHaveBeenCalledWith('/');
    expect(received).toEqual([{ query: '我今天有什么安排？' }]);

    fireEvent.click(screen.getByRole('button', { name: '打开助手' }));
    expect(received[1]).toEqual({ query: '' });
  });

  it('列表为空时不渲染', async () => {
    api().getAssistantContext.mockResolvedValue({ data: { quick_prompts: [] } });
    render(<AssistantCard />);
    await waitFor(() => expect(api().getAssistantContext).toHaveBeenCalled());
    expect(screen.queryByTestId('dashboard-assistant-card')).not.toBeInTheDocument();
  });

  it('接口失败时不渲染', async () => {
    api().getAssistantContext.mockRejectedValue(new Error('down'));
    render(<AssistantCard />);
    await waitFor(() => expect(api().getAssistantContext).toHaveBeenCalled());
    expect(screen.queryByTestId('dashboard-assistant-card')).not.toBeInTheDocument();
  });
});
