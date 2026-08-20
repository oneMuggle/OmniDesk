import * as api from './scores';
import client from './client';

jest.mock('./client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() },
}));

describe('scores API', () => {
  beforeEach(() => jest.clearAllMocks());

  it('list/create/get/update score 使用正确路径', () => {
    api.listScores({ cycle: 1 });
    api.createScore({ cycle: 1, joint_student: 2, score: 90 });
    api.getScore(5);
    api.updateScore(5, { comment: '很好' });
    expect(client.get).toHaveBeenNthCalledWith(1, 'scores/', { params: { cycle: 1 } });
    expect(client.post).toHaveBeenCalledWith('scores/', { cycle: 1, joint_student: 2, score: 90 });
    expect(client.get).toHaveBeenNthCalledWith(2, 'scores/5/');
    expect(client.patch).toHaveBeenCalledWith('scores/5/', { comment: '很好' });
  });

  it('unlockScore 使用解锁动作', () => {
    api.unlockScore(5);
    expect(client.post).toHaveBeenCalledWith('scores/5/unlock/');
  });
});
