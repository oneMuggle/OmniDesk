import { getAllKeys } from '../userManagementUtils';

describe('getAllKeys', () => {
    it('空树返回空数组', () => {
        expect(getAllKeys([])).toEqual([]);
    });

    it('收集无子节点树的所有 key', () => {
        const tree = [
            { key: 1, title: '权限A' },
            { key: 2, title: '权限B' },
        ];
        expect(getAllKeys(tree)).toEqual([1, 2]);
    });

    it('递归收集嵌套树的所有 key（含父节点）', () => {
        const tree = [
            {
                key: 'group1',
                title: '组1',
                children: [
                    { key: 11, title: '权限A' },
                    { key: 12, title: '权限B' },
                ],
            },
            {
                key: 'group2',
                title: '组2',
                children: [
                    {
                        key: 21,
                        title: '子组',
                        children: [{ key: 211, title: '权限C' }],
                    },
                ],
            },
        ];
        expect(getAllKeys(tree)).toEqual(['group1', 11, 12, 'group2', 21, 211]);
    });

    it('混合节点：叶子与子树并存时全部收集', () => {
        const tree = [
            { key: 1, title: '叶子' },
            { key: 2, title: '父', children: [{ key: 3, title: '子' }] },
        ];
        expect(getAllKeys(tree)).toEqual([1, 2, 3]);
    });
});
