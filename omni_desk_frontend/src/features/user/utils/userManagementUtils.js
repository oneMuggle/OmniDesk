/**
 * userManagementUtils — UserManagementPage 拆分出的纯函数
 *
 * 由 UserManagementPage.jsx 拆分而来,承接无 React 依赖的工具函数。
 */
const getAllKeys = (tree) => {
    let keys = [];
    for (const node of tree) {
        keys.push(node.key);
        if (node.children) {
            keys = keys.concat(getAllKeys(node.children));
        }
    }
    return keys;
};

export { getAllKeys };
