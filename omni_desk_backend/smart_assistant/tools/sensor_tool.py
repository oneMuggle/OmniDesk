from sensor_management.models import Sensor, SensorCalibration
from .base import BaseTool


class SensorTool(BaseTool):
    name = "sensor_query"
    description = "查询传感器数据和告警"
    intent_type = "sensor_query"

    def execute(self, query: str, context: dict = None) -> dict:
        """查询传感器信息和校准状态"""
        keywords = query.replace("搜索", "").replace("查找", "").replace("传感器", "").replace("设备", "").strip()

        # 按名称或编号搜索
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
