"""
测试数据 Seeder 基类和注册机制

扩展方式：
1. 新建 seeder 文件，继承 BaseSeeder
2. 实现 seed() 方法，返回 (label, count) 元组
3. 在 seeders 目录下即可被自动发现
"""


class BaseSeeder:
    """
    Seeder 基类，提供通用模式：
    - 依赖声明
    - 优雅降级（模型不存在时跳过）
    - 字段变更兼容（UnknownFieldError 处理）
    """

    name = ""  # seeder 名称，子类必须设置
    order = 100  # 执行顺序，越小越先执行
    models = []  # 此 seeder 创建的模型列表，子类应声明

    def __init__(self, context=None):
        self.context = context or {}
        self.created_count = 0

    def safe_get_or_create(self, model, **kwargs):
        """
        带容错的 get_or_create：
        - 自动过滤模型中已不存在的字段（兼容字段删除）
        - 给出警告提示
        """
        from django.db import models as db_models

        valid_fields = {f.name for f in model._meta.get_fields() if isinstance(f, db_models.Field)}

        # 过滤 defaults 中的无效字段
        defaults = kwargs.get("defaults", {})
        safe_defaults = {k: v for k, v in defaults.items() if k in valid_fields}
        safe_kwargs = {k: v for k, v in kwargs.items() if k not in ("defaults",) and k in valid_fields}

        dropped = set(defaults.keys()) - set(safe_defaults.keys())
        if dropped:
            from django.utils.termcolors import colorize

            print(colorize(f"    警告: {model.__name__} 已不存在字段 {dropped}，已跳过", fg="yellow"))

        return model.objects.get_or_create(**safe_kwargs, defaults=safe_defaults)

    def has_models(self, *model_classes):
        """检查所有模型类是否都存在"""
        for model_cls in model_classes:
            if model_cls is None:
                return False
        return True

    def seed(self):
        """子类实现此方法，返回 (label, count) 元组"""
        raise NotImplementedError

    def __repr__(self):
        return f"<Seeder: {self.name} (order={self.order})>"
