"""
插件沙箱执行模块
通过子进程隔离 + 资源限制实现安全执行环境。
"""
import os
import logging
from .plugin_loader import execute_plugin, cleanup_plugin_dir

logger = logging.getLogger(__name__)


def execute_plugin_safely(extract_dir, manifest, input_data):
    """安全执行插件：验证 manifest、设置资源限制、执行并记录日志"""
    entry_point = manifest.get('entry_point', '')
    timeout = manifest.get('timeout_seconds', 30)

    try:
        returncode, result, stderr, elapsed_ms = execute_plugin(
            extract_dir=extract_dir,
            entry_point=entry_point,
            input_data=input_data,
            timeout=timeout,
        )

        if returncode == 0:
            return {
                'success': True,
                'result': result,
                'execution_time_ms': elapsed_ms,
            }
        else:
            return {
                'success': False,
                'error': stderr or f'插件退出码: {returncode}',
                'execution_time_ms': elapsed_ms,
            }

    except FileNotFoundError as e:
        return {'success': False, 'error': f'插件文件缺失: {e}'}
    except Exception as e:
        logger.exception('插件执行异常')
        return {'success': False, 'error': str(e)}
    finally:
        cleanup_plugin_dir(extract_dir)
