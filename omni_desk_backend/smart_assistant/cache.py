"""智能助手结果缓存：缓存意图分类和工具查询结果，减少重复 LLM 调用。"""
import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# 缓存时长
INTENT_CACHE_TTL = 3600      # 意图分类: 1 小时
TOOL_CACHE_TTL = 1800        # 工具结果: 30 分钟
ANSWER_CACHE_TTL = 7200      # 常见回答: 2 小时

CACHE_PREFIX = 'smart_assistant:cache:'


def _key(*parts):
    """生成缓存 key。"""
    raw = ':'.join(str(p) for p in parts)
    return CACHE_PREFIX + hashlib.md5(raw.encode()).hexdigest()[:16]


def get_cached_intent(query, schemas):
    """尝试从缓存获取意图分类结果。"""
    schemas_sig = ','.join(s['name'] for s in sorted(schemas, key=lambda x: x['name']))
    key = _key('intent', query, schemas_sig)
    return cache.get(key)


def cache_intent(query, schemas, intent):
    """缓存意图分类结果。"""
    schemas_sig = ','.join(s['name'] for s in sorted(schemas, key=lambda x: x['name']))
    key = _key('intent', query, schemas_sig)
    cache.set(key, intent, INTENT_CACHE_TTL)


def get_cached_tool_result(tool_name, query, context_sig=''):
    """尝试从缓存获取工具结果。"""
    key = _key('tool', tool_name, query, context_sig)
    return cache.get(key)


def cache_tool_result(tool_name, query, result, context_sig=''):
    """缓存工具查询结果。"""
    if not isinstance(result, dict) or not result.get('found'):
        return  # 仅缓存成功结果
    key = _key('tool', tool_name, query, context_sig)
    cache.set(key, result, TOOL_CACHE_TTL)


def get_cached_answer(query, intent, history_sig=''):
    """尝试从缓存获取回答。"""
    key = _key('answer', query, intent, history_sig)
    return cache.get(key)


def cache_answer(query, intent, answer, history_sig=''):
    """缓存回答结果。"""
    key = _key('answer', query, intent, history_sig)
    cache.set(key, answer, ANSWER_CACHE_TTL)
