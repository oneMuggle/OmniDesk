"""
Seeder 自动注册机制

新增 seeder 的步骤：
1. 在此文件末尾的 SEEDER_REGISTRY 中添加一行
2. 运行 python manage.py seed_data 即可自动执行
"""


# ─── Seeder 注册列表 ───
# 每个元组: (模块路径, seeder类名, 是否默认启用)
# 当新增 seeder 时，在此处添加一行即可
SEEDER_REGISTRY = [
    # 人员管理
    ("events.management.seeders.personnel_seeder", "PersonnelSeeder", True),
    # 试验与排班
    ("events.management.seeders.trial_schedule_seeder", "TrialScheduleSeeder", True),
    # 会议室
    ("events.management.seeders.meeting_room_seeder", "MeetingRoomSeeder", True),
    # 传感器
    ("events.management.seeders.sensor_seeder", "SensorSeeder", True),
    # 项目与文档
    ("events.management.seeders.project_seeder", "ProjectSeeder", True),
    # 其他辅助数据
    ("events.management.seeders.misc_seeder", "MiscSeeder", True),
]


def discover_seeders(context, enabled_names=None):
    """
    动态加载并实例化所有注册的 seeder。

    Args:
        context: 传递给每个 seeder 的上下文字典
        enabled_names: 启用的 seeder name 列表，None 表示全部启用

    Returns:
        按 order 排序的 seeder 实例列表
    """
    import importlib

    seeders = []
    for module_path, class_name, default_enabled in SEEDER_REGISTRY:
        if enabled_names and class_name not in enabled_names:
            continue
        if not default_enabled and not enabled_names:
            continue

        try:
            mod = importlib.import_module(module_path)
            seeder_cls = getattr(mod, class_name)
            seeders.append(seeder_cls(context=context))
        except ModuleNotFoundError as e:
            from django.utils.termcolors import colorize
            print(colorize(f"  跳过 {class_name}: 模块 {module_path} 不存在", fg="yellow"))
            print(colorize(f"    原因: {e}", fg="yellow"))

    return sorted(seeders, key=lambda s: s.order)
