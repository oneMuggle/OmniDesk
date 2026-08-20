import * as api from './students';
import client from './client';

jest.mock('./client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
}));

describe('students API', () => {
  beforeEach(() => jest.clearAllMocks());

  it('listStudents 支持查询参数', () => {
    api.listStudents({ is_active: true });
    expect(client.get).toHaveBeenCalledWith('students/', { params: { is_active: true } });
  });

  it('create/update/delete student 使用对应 HTTP 方法', () => {
    api.createStudent({ student_id: 'S1' });
    api.updateStudent(1, { is_active: false });
    api.deleteStudent(1);
    expect(client.post).toHaveBeenCalledWith('students/', { student_id: 'S1' });
    expect(client.patch).toHaveBeenCalledWith('students/1/', { is_active: false });
    expect(client.delete).toHaveBeenCalledWith('students/1/');
  });

  it('graduateStudent 和 personnel pool 使用正确路径', () => {
    api.graduateStudent(2);
    api.listPersonnelPool();
    expect(client.post).toHaveBeenCalledWith('students/2/graduate/');
    expect(client.get).toHaveBeenCalledWith('personnel-pool/');
  });
});
