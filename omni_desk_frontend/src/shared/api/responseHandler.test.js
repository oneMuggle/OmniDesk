import { handleResponse, handleError, extractResults } from './responseHandler';

jest.mock('antd', () => ({
  message: { error: jest.fn() },
}));

describe('extractResults', () => {
  it('DRF 分页形态 {results} → 返回 results 数组', () => {
    const data = { results: [{ id: 1 }, { id: 2 }], count: 2 };
    expect(extractResults(data)).toEqual([{ id: 1 }, { id: 2 }]);
  });

  it('裸数组形态 → 原样返回', () => {
    const data = [{ id: 1 }, { id: 2 }];
    expect(extractResults(data)).toEqual(data);
    expect(extractResults(data)).toBe(data);
  });

  it('{results: []}(空页)→ 返回空数组', () => {
    expect(extractResults({ results: [], count: 0 })).toEqual([]);
  });

  it('null / undefined → 返回 []', () => {
    expect(extractResults(null)).toEqual([]);
    expect(extractResults(undefined)).toEqual([]);
  });

  it('非对象非数组输入(字符串/数字)→ 返回 []', () => {
    expect(extractResults('oops')).toEqual([]);
    expect(extractResults(42)).toEqual([]);
  });

  it('results 非数组({results: null})→ 返回 []', () => {
    expect(extractResults({ results: null })).toEqual([]);
  });

  it('无 results 键的普通对象 → 返回 []', () => {
    expect(extractResults({ count: 5 })).toEqual([]);
  });
});

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
