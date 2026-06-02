from sensor_management.models import Sensor, SensorCalibration
from .base import BaseTool


class SensorTool(BaseTool):
    name = "sensor_query"
    description = "查询传感器数据和告警"
    intent_type = "sensor_query"

    def execute(self, query: str, context: dict = None) -> dict:
        """查询传感器信息和校准状态"""
        keywords = query.replace("搜索", "").replace("查找", "").replace(
            "传感器", "").replace("设备", "").strip()

        # 按名称或编号搜索
        sensors = Sensor.objects.filter(
            name__icontains=keywords
        ).select_related('category', 'storage_location')[:10]

        if not sensors.exists():
            # 如果没有关键词，返回传感器统计
            if not keywords:
                total = Sensor.objects.count()
                active = Sensor.objects.filter(is_active=True).count()
                return {
                    'found': True,
                    'summary': True,
                    'total_sensors': total,
                    'active_sensors': active,
                    'message': f'共有 {total} 个传感器，其中 {active} 个在线。',
                }
            return {
                'found': False,
                'message': f'未找到与 "{keywords}" 相关的传感器',
            }

        results = []
        for s in sensors:
            # 获取最近的校准记录
            latest_calibration = SensorCalibration.objects.filter(
                sensor=s
            ).order_by('-calibration_date').first()

            results.append({
                'name': s.name,
                'model': s.model,
                'serial_number': s.serial_number,
                'category': s.category.name if s.category else '未分类',
                'status': s.status,
                'is_active': s.is_active,
                'location': s.storage_location.name if s.storage_location else '未分配',
                'last_calibration': str(latest_calibration.calibration_date.date())
                if latest_calibration else '未校准',
                'calibration_status': latest_calibration.result
                if latest_calibration else '未知',
            })

        return {
            'found': True,
            'count': len(results),
            'sensors': results,
        }
