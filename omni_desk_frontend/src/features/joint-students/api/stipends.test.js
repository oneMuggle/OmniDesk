import * as api from './stipends';
import client from './client';

jest.mock('./client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
}));

describe('stipends API', () => {
  beforeEach(() => jest.clearAllMocks());

  it('list/get stipend 使用正确路径', () => {
    api.listStipends({ cycle: 2 });
    api.getStipend(8);
    expect(client.get).toHaveBeenNthCalledWith(1, 'stipends/', { params: { cycle: 2 } });
    expect(client.get).toHaveBeenNthCalledWith(2, 'stipends/8/');
  });

  it('lockStipend 传 notes 或空对象', () => {
    api.lockStipend(8, '已复核');
    api.lockStipend(9);
    expect(client.post).toHaveBeenNthCalledWith(1, 'stipends/8/lock/', { notes: '已复核' });
    expect(client.post).toHaveBeenNthCalledWith(2, 'stipends/9/lock/', {});
  });
});
