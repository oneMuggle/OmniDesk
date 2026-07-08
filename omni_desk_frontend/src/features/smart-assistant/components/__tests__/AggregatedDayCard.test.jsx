import React from 'react';
import { render, screen } from '@testing-library/react';
import AggregatedDayCard from '../AggregatedDayCard';

describe('AggregatedDayCard', () => {
  test('renders summary text', () => {
    render(<AggregatedDayCard summary="共 3 项:排班 2 条、会议 1 条" items={[]} moduleCounts={{}} />);
    expect(screen.getByText(/共 3 项/)).toBeInTheDocument();
  });

  test('renders module count badges', () => {
    const items = [
      { type: 'schedule_query', module: '排班', data: { duty_date: '2026-07-08' }, sort_key: '2026-07-08' },
      { type: 'meeting_room_query', module: '会议室', data: { name: 'R1' }, sort_key: '2026-07-09' },
    ];
    render(<AggregatedDayCard summary="共 2 项" items={items} moduleCounts={{ 排班: 1, 会议室: 1 }} />);
    expect(screen.getByText('排班')).toBeInTheDocument();
    expect(screen.getByText('会议室')).toBeInTheDocument();
  });

  test('renders empty state when no items', () => {
    render(<AggregatedDayCard summary="未找到相关信息" items={[]} moduleCounts={{}} />);
    expect(screen.getByText(/未找到/)).toBeInTheDocument();
  });

  test('groups items by module', () => {
    const items = [
      { type: 'schedule_query', module: '排班', data: { duty_date: 'd1' }, sort_key: '2026-07-08' },
      { type: 'schedule_query', module: '排班', data: { duty_date: 'd2' }, sort_key: '2026-07-09' },
      { type: 'meeting_room_query', module: '会议室', data: { name: 'R1' }, sort_key: '2026-07-09' },
    ];
    const { container } = render(
      <AggregatedDayCard summary="共 3 项" items={items} moduleCounts={{ 排班: 2, 会议室: 1 }} />
    );
    const groups = container.querySelectorAll('[data-testid="module-group"]');
    expect(groups.length).toBe(2);
  });

  test('renders loading skeleton when isLoading', () => {
    const { container } = render(
      <AggregatedDayCard summary="" items={[]} moduleCounts={{}} isLoading />
    );
    expect(container.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  test('renders error state when error', () => {
    render(<AggregatedDayCard summary="" items={[]} moduleCounts={{}} error="服务异常" />);
    expect(screen.getByText(/服务异常/)).toBeInTheDocument();
  });
});