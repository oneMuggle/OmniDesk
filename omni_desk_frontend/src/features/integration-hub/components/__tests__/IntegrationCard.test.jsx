/**
 * IntegrationCard 最小单测(R4-D3)。
 *
 * 覆盖三种 integration_type 的标签/按钮映射:
 * iframe → 「打开」,api → 「调用」,widget → 无操作按钮;缺失 description 的回退。
 */
import { render, screen, fireEvent } from '@testing-library/react';
import IntegrationCard from '../IntegrationCard';

describe('IntegrationCard', () => {
  it('渲染名称与描述', () => {
    render(<IntegrationCard
      service={{ name: '企业微信', description: '消息推送通道', integration_type: 'widget' }}
    />);

    expect(screen.getByText('企业微信')).toBeInTheDocument();
    expect(screen.getByText('消息推送通道')).toBeInTheDocument();
  });

  it('无描述时回退为「暂无描述」', () => {
    render(<IntegrationCard
      service={{ name: '钉钉', integration_type: 'api' }}
    />);

    expect(screen.getByText('暂无描述')).toBeInTheDocument();
  });

  it('iframe 类型 → 标签 + 「打开」按钮触发 onView', () => {
    const onView = jest.fn();
    const onExecute = jest.fn();
    const service = { name: '报表中心', integration_type: 'iframe' };

    render(<IntegrationCard service={service} onView={onView} onExecute={onExecute} />);

    expect(screen.getByText('iframe 嵌入')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /打\s*开/ }));

    expect(onView).toHaveBeenCalledWith(service);
    expect(onExecute).not.toHaveBeenCalled();
  });

  it('api 类型 → 标签 + 「调用」按钮触发 onExecute', () => {
    const onView = jest.fn();
    const onExecute = jest.fn();
    const service = { name: '数据接口', integration_type: 'api' };

    render(<IntegrationCard service={service} onView={onView} onExecute={onExecute} />);

    expect(screen.getByText('API 代理')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /调\s*用/ }));

    expect(onExecute).toHaveBeenCalledWith(service);
    expect(onView).not.toHaveBeenCalled();
  });

  it('widget 类型 → 不渲染操作按钮', () => {
    render(<IntegrationCard
      service={{ name: '天气', integration_type: 'widget' }}
      onView={jest.fn()}
      onExecute={jest.fn()}
    />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});