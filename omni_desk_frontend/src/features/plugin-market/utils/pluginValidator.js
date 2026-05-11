const REQUIRED_FIELDS = ['name', 'version', 'entry_point', 'protocol'];

export function validateManifest(jsonString) {
  if (!jsonString || !jsonString.trim()) {
    return '';
  }

  let parsed;
  try {
    parsed = JSON.parse(jsonString);
  } catch {
    return '清单 JSON 格式无效，请检查语法';
  }

  for (const field of REQUIRED_FIELDS) {
    if (!parsed[field]) {
      return `清单缺少必需字段: ${field}`;
    }
  }

  if (parsed.protocol !== 'stdio') {
    return '仅支持 stdio 协议';
  }

  if (parsed.timeout && (typeof parsed.timeout !== 'number' || parsed.timeout <= 0)) {
    return 'timeout 必须是正整数';
  }

  return '';
}

export function validatePluginName(name) {
  if (!name || name.trim().length === 0) {
    return '插件名称不能为空';
  }
  if (name.length > 255) {
    return '插件名称不能超过 255 个字符';
  }
  return '';
}
