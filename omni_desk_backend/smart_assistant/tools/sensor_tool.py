from sensor_management.models import Sensor, SensorCalibration
from .base import BaseTool


class SensorTool(BaseTool):
    name = "sensor_query"
    description = "查询传感器数据和告警"
    intent_type = "sensor_query"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """查询传感器信息和校准状态。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用
          (C-1 修复:复用 scoped queryset,确保 SELF/DEPARTMENT/GLOBAL 生效)。
        """
        # 新路径(scope-aware):用调用方注入的 scoped queryset 替代全量表查询
        if qs is not None and scope is not None:
            search_query = params.get("query") if isinstance(params, dict) and params.get("query") else (query or "")
            keywords = self._extract_keywords(search_query)
            sensors = qs.filter(name__icontains=keywords)[:10]
        else:
            keywords = self._extract_keywords(query or "")
            sensors = Sensor.objects.filter(name__icontains=keywords).select_related("sensor_category", "location")[:10]

        if not sensors.exists():
            # 如果没有关键词，返回传感器统计
            if not keywords:
                total = Sensor.objects.count()
                active = Sensor.objects.filter(status="in_use").count()
                return {
                    "found": True,
                    "summary": True,
                    "total_sensors": total,
                    "active_sensors": active,
                    "message": f"共有 {total} 个传感器，其中 {active} 个在线。",
                }
            return {
                "found": False,
                "message": f'未找到与 "{keywords}" 相关的传感器',
            }

        results = []
        for s in sensors:
            # 获取最近的校准记录
            latest_calibration = SensorCalibration.objects.filter(sensor=s).order_by("-calibration_date").first()

            results.append(
                {
                    "name": s.name,
                    "model": s.sensor_number,
                    "serial_number": s.serial_number,
                    "category": s.sensor_category.name if s.sensor_category else "未分类",
                    "status": s.status,
                    "is_active": s.status == "in_use",
                    "location": s.location.name if s.location else "未分配",
                    "last_calibration": str(latest_calibration.calibration_date.date())
                    if latest_calibration
                    else "未校准",
                    "calibration_status": latest_calibration.result if latest_calibration else "未知",
                }
            )

        return {
            "found": True,
            "count": len(results),
            "sensors": results,
        }

    @staticmethod
    def _extract_keywords(query: str) -> str:
        """从查询文本中剥离停用词(新旧路径共用,保证关键词口径一致)。"""
        return query.replace("搜索", "").replace("查找", "").replace("传感器", "").replace("设备", "").strip()

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 查询传感器数据和校准状态。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询传感器数据(名称、编号、状态、最近校准)和校准结果。"
                    "示例 query: '查温湿度传感器'、'所有在校传感器统计'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词,匹配名称/编号;空则返回汇总统计",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["in_use", "idle", "broken", "retired"],
                            "description": "按传感器状态过滤(可选)",
                        },
                        "category": {
                            "type": "string",
                            "description": "按传感器分类精确过滤(可选)",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        """返回未过滤的传感器 QuerySet(主模型;execute 同时查 SensorCalibration)。"""
        return Sensor.objects.select_related("sensor_category", "location").all()

    def _scope_self(self, qs, ctx):
        """本人范围:传感器是公共设备库存,无"本人"语义;返回空 QuerySet。"""
        return qs.none()
