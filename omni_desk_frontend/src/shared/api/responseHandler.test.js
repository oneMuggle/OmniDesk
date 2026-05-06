import { handleResponse, handleError } from './responseHandler';

jest.mock('antd', () => ({
  message: { error: jest.fn() },
}));

describe('responseHandler', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('handleResponse', () => {
    it('should return data for 200 status', () => {
      const response = { status: 200, data: { id: 1 } };
      expect(handleResponse(response)).toEqual({ id: 1 });
    });

    it('should return data for 201 status', () => {
      const response = { status: 201, data: { created: true } };
      expect(handleResponse(response)).toEqual({ created: true });
    });

    it('should throw error for 400 status', () => {
      const response = { status: 400, statusText: 'Bad Request', data: {} };
      expect(() => handleResponse(response)).toThrow('Bad Request');
    });

    it('should throw error for 500 status', () => {
      const response = { status: 500, statusText: 'Server Error', data: {} };
      expect(() => handleResponse(response)).toThrow('Server Error');
    });
  });

  describe('handleError', () => {
    it('should throw enhanced error with message', async () => {
      const error = new Error('Network error');
      await expect(() => handleError(error)).toThrow('Network error');
    });

    it('should use duty_date from response data', async () => {
      const error = new Error('Validation failed');
      error.response = { data: { duty_date: ['日期已存在'] } };
      await expect(() => handleError(error)).toThrow('日期已存在');
    });

    it('should use detail from response data', async () => {
      const error = new Error('Error');
      error.response = { data: { detail: '具体错误信息' } };
      await expect(() => handleError(error)).toThrow('具体错误信息');
    });

    it('should stringify response data if no specific field', async () => {
      const error = new Error('Error');
      error.response = { data: { foo: 'bar' } };
      await expect(() => handleError(error)).toThrow(/foo/);
    });

    it('should prefix map error message', async () => {
      const error = new Error('map is not a function');
      await expect(() => handleError(error)).toThrow('数据处理失败');
    });

    it('should not show toast when showToast is false', async () => {
      const { message } = require('antd');
      const error = new Error('Silent error');
      try {
        await handleError(error, false);
      } catch (e) {
        // expected
      }
      expect(message.error).not.toHaveBeenCalled();
    });

    it('should show toast when showToast is true', async () => {
      const { message } = require('antd');
      const error = new Error('Visible error');
      try {
        await handleError(error, true);
      } catch (e) {
        // expected
      }
      expect(message.error).toHaveBeenCalledWith('Visible error');
    });
  });
});
