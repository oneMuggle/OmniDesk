import apiClient from '../../../shared/api/apiClient';
import { createJointStudentsClient } from './client';

jest.mock('../../../shared/api/apiClient', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
}));

describe('createJointStudentsClient', () => {
  it('默认复用项目共享 API client', () => {
    expect(createJointStudentsClient()).toBe(apiClient);
  });

  it('允许测试或调用方注入自定义 client', () => {
    const customClient = { get: jest.fn() };
    expect(createJointStudentsClient(customClient)).toBe(customClient);
  });

  it('联培生 API 默认导出共享 client', async () => {
    const { default: client } = await import('./client');
    expect(client).toBe(apiClient);
  });
});
