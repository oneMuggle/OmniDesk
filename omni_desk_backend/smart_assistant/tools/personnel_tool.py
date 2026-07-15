from personnel.models import Personnel
from .base import BaseTool


class PersonnelTool(BaseTool):
    name = "personnel_query"
    description = "查询人员信息（姓名、部门、职位、状态）"
    intent_type = "personnel_query"

    def execute(self, query: str, context: dict | None = None) -> dict:
        """搜索人员信息，仅返回脱敏字段"""
        keywords = query.replace("谁", "").replace("是", "").replace("的", "").strip()

        personnel_list = Personnel.objects.filter(name__icontains=keywords).select_related("position")[:10]

        if not personnel_list.exists():
            return {
                "found": False,
                "message": f'未找到与 "{keywords}" 匹配的人员',
            }

        results = []
        for p in personnel_list:
            results.append(
                {
                    "name": p.name,
                    "department": p.department or "未分配",
                    "position": p.position.name if p.position else "未设置",
                    "status": p.get_status_display(),
                    "phone_number": p.phone_number or "未登记",
                }
            )

        return {
            "found": True,
            "count": len(results),
            "personnel": results,
        }

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "intent_type": self.intent_type,
        }
