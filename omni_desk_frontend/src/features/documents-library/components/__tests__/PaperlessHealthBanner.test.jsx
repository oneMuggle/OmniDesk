/**
 * PaperlessHealthBanner 渲染测试(R4-D1)。
 *
 * 通过 mock usePaperlessHealth,隔离 hook 行为,断言三态渲染:
 * loading / 健康 → 不渲染;不健康 → 告警。
 */
import { render, screen } from '@testing-library/react';
import PaperlessHealthBanner from '../PaperlessHealthBanner';
import { usePaperlessHealth } from '../../hooks/usePaperlessHealth';

jest.mock('../../hooks/usePaperlessHealth', () => ({
  usePaperlessHealth: jest.fn(),
}));

describe('PaperlessHealthBanner', () => {
  it('健康时不渲染任何内容', () => {
    usePaperlessHealth.mockReturnValue({ isHealthy: true, loading: false });

    const { container } = render(<PaperlessHealthBanner />);

    expect(container).toBeEmptyDOMElement();
  });

  it('仍在加载时不渲染(避免闪烁告警)', () => {
    usePaperlessHealth.mockReturnValue({ isHealthy: true, loading: true });

    const { container } = render(<PaperlessHealthBanner />);

    expect(container).toBeEmptyDOMElement();
  });

  it('服务不可用时展示告警', () => {
    usePaperlessHealth.mockReturnValue({ isHealthy: false, loading: false });

    render(<PaperlessHealthBanner />);

    expect(screen.getByText('paperless 文档服务暂不可用')).toBeInTheDocument();
    expect(screen.getByText(/新上传的文档将稍后自动同步/)).toBeInTheDocument();
  });
});