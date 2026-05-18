from projects.models import Project
from .base import BaseTool


class ProjectTool(BaseTool):
    name = "project_status"
    description = "查询项目进度/状态/负责人"
    intent_type = "project_status"

    def execute(self, query: str, context: dict = None) -> dict:
        """查询项目信息"""
        keywords = query.replace("搜索", "").replace("查找", "").replace("项目", "").strip()

        projects = Project.objects.filter(
            name__icontains=keywords
        ).select_related('manager')[:10]

        if not projects.exists():
            return {
                'found': False,
                'message': f'未找到与 "{keywords}" 相关的项目',
            }

        results = []
        for p in projects:
            results.append({
                'name': p.name,
                'description': p.description[:100] + ('...' if len(p.description) > 100 else ''),
                'manager': p.manager.username if p.manager else '未指定',
                'status': p.status,
                'start_date': str(p.start_date) if p.start_date else '未设置',
                'end_date': str(p.end_date) if p.end_date else '未设置',
            })

        return {
            'found': True,
            'count': len(results),
            'projects': results,
        }
