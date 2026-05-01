import * as sequenceApi from './sequenceApi';
import apiClient from './apiClient';

jest.mock('./apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

describe('sequenceApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Personnel Sequence', () => {
    it('should get all personnel sequences', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });
      await sequenceApi.getPersonnelSequences();
      expect(apiClient.get).toHaveBeenCalledWith('events/personnel-sequences/');
    });

    it('should get single personnel sequence', async () => {
      apiClient.get.mockResolvedValue({ data: { id: 1 } });
      await sequenceApi.getPersonnelSequenceDetails(1);
      expect(apiClient.get).toHaveBeenCalledWith('events/personnel-sequences/1/');
    });

    it('should create personnel sequence', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1 } });
      await sequenceApi.createPersonnelSequence({ personnel: [1, 2] });
      expect(apiClient.post).toHaveBeenCalledWith('events/personnel-sequences/', { personnel: [1, 2] });
    });

    it('should update personnel sequence', async () => {
      apiClient.put.mockResolvedValue({ data: { id: 1 } });
      await sequenceApi.updatePersonnelSequence(1, { personnel: [2, 1] });
      expect(apiClient.put).toHaveBeenCalledWith('events/personnel-sequences/1/', { personnel: [2, 1] });
    });

    it('should delete personnel sequence', async () => {
      apiClient.delete.mockResolvedValue({});
      await sequenceApi.deletePersonnelSequence(1);
      expect(apiClient.delete).toHaveBeenCalledWith('events/personnel-sequences/1/');
    });
  });

  describe('Leader Sequence', () => {
    it('should get all leader sequences', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });
      await sequenceApi.getLeaderSequences();
      expect(apiClient.get).toHaveBeenCalledWith('events/leader-sequences/');
    });

    it('should get single leader sequence', async () => {
      apiClient.get.mockResolvedValue({ data: { id: 1 } });
      await sequenceApi.getLeaderSequenceDetails(1);
      expect(apiClient.get).toHaveBeenCalledWith('events/leader-sequences/1/');
    });

    it('should create leader sequence', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1 } });
      await sequenceApi.createLeaderSequence({ leaders: [1, 2] });
      expect(apiClient.post).toHaveBeenCalledWith('events/leader-sequences/', { leaders: [1, 2] });
    });

    it('should update leader sequence', async () => {
      apiClient.put.mockResolvedValue({ data: { id: 1 } });
      await sequenceApi.updateLeaderSequence(1, { leaders: [2, 1] });
      expect(apiClient.put).toHaveBeenCalledWith('events/leader-sequences/1/', { leaders: [2, 1] });
    });

    it('should delete leader sequence', async () => {
      apiClient.delete.mockResolvedValue({});
      await sequenceApi.deleteLeaderSequence(1);
      expect(apiClient.delete).toHaveBeenCalledWith('events/leader-sequences/1/');
    });
  });
});
