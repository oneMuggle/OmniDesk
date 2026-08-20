import * as api from './cycles';
import client from './client';

jest.mock('./client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
}));

describe('cycles API', () => {
  beforeEach(() => jest.clearAllMocks());

  it('list/get cycles 和手动触发使用正确路径', () => {
    api.listCycles({ status: 'collecting' });
    api.getCycle(4);
    api.triggerCycle({ year: 2026, month: 8 });
    expect(client.get).toHaveBeenNthCalledWith(1, 'cycles/', { params: { status: 'collecting' } });
    expect(client.get).toHaveBeenNthCalledWith(2, 'cycles/4/');
    expect(client.post).toHaveBeenCalledWith('cycles/trigger/', { year: 2026, month: 8 });
  });

  it('force close 和周期关联查询使用正确路径', () => {
    api.forceCloseCycle(4);
    api.listCycleScores(4, { page: 2 });
    api.listCycleStipends(4);
    expect(client.post).toHaveBeenCalledWith('cycles/4/force_close/');
    expect(client.get).toHaveBeenNthCalledWith(1, 'cycles/4/scores/', { params: { page: 2 } });
    expect(client.get).toHaveBeenNthCalledWith(2, 'cycles/4/stipends/', { params: undefined });
  });
});
