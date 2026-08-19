import { buildSequencePayload } from '../sequenceUtils';

describe('buildSequencePayload', () => {
  // 对应原 handleSave 的 4 分支:create/update × personnel/leader
  test('人员顺序 CREATE:rename sequence → personnel,去掉 sequence 字段', () => {
    const values = { name: '新人员顺序', sequence: [1, 2] };
    expect(buildSequencePayload(values, false)).toEqual({
      name: '新人员顺序',
      personnel: [1, 2],
    });
  });

  test('人员顺序 UPDATE:合并 sequence + holiday_sequence 去重为 personnel,保留原字段', () => {
    const values = {
      id: 1,
      name: '人员顺序',
      sequence: [1, 2],
      holiday_sequence: [2, 3],
    };
    expect(buildSequencePayload(values, false)).toEqual({
      id: 1,
      name: '人员顺序',
      sequence: [1, 2],
      holiday_sequence: [2, 3],
      personnel: [1, 2, 3],
    });
  });

  test('人员顺序 UPDATE 无 holiday_sequence 时仅用 sequence', () => {
    const values = { id: 2, name: '人员顺序', sequence: [4, 5] };
    expect(buildSequencePayload(values, false)).toEqual({
      id: 2,
      name: '人员顺序',
      sequence: [4, 5],
      personnel: [4, 5],
    });
  });

  test('领导顺序 CREATE:补 personnel 字段,保留 sequence', () => {
    const values = { name: '新领导顺序', sequence: [3] };
    expect(buildSequencePayload(values, true)).toEqual({
      name: '新领导顺序',
      sequence: [3],
      personnel: [3],
    });
  });

  test('领导顺序 UPDATE:与 CREATE 一致补 personnel 字段', () => {
    const values = { id: 1, name: '领导顺序', sequence: [3] };
    expect(buildSequencePayload(values, true)).toEqual({
      id: 1,
      name: '领导顺序',
      sequence: [3],
      personnel: [3],
    });
  });
});
