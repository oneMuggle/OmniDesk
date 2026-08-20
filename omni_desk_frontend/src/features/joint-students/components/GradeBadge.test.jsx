import { render, screen } from '@testing-library/react';
import GradeBadge from './GradeBadge';

describe('GradeBadge', () => {
  it('A 档使用绿色 Tag', () => {
    render(<GradeBadge grade="A" />);
    const tag = screen.getByText('A 档');
    expect(tag).toBeInTheDocument();
    expect(tag.className).toMatch(/ant-tag-green/);
  });

  it('B 档使用 default Tag', () => {
    render(<GradeBadge grade="B" />);
    const tag = screen.getByText('B 档');
    expect(tag).toBeInTheDocument();
    expect(tag.className).toMatch(/ant-tag/);
  });

  it('未评定走默认分支', () => {
    render(<GradeBadge grade="unknown" />);
    expect(screen.getByText('未评定')).toBeInTheDocument();
  });
});
