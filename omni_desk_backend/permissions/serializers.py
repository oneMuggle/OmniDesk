from django.contrib.auth.models import Group
from rest_framework import serializers

from .models import PageRoute


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]


class PageRouteSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = PageRoute
        fields = ["id", "name", "path", "component", "parent", "children"]

    def get_children(self, obj):
        children = PageRoute.objects.filter(parent=obj)
        if children.exists():
            return PageRouteSerializer(children, many=True).data
        return []


# ---- 内存建树辅助函数:消除 PageRouteSerializer 递归 get_children 的逐节点 N+1 ----


def build_page_route_children_map(routes):
    """按 parent_id 分组聚合全表路由(输入需已按 id 排序以保证兄弟节点顺序与原 DB 行为一致)。"""
    children_map = {}
    for route in routes:
        children_map.setdefault(route.parent_id, []).append(route)
    return children_map


def build_page_route_children(children_map, parent_id):
    """递归构建 children 子树,节点字段结构与 PageRouteSerializer 输出完全一致。"""
    return [build_page_route_node(node, children_map) for node in children_map.get(parent_id, [])]


def build_page_route_node(route, children_map):
    """构建单个节点的序列化 dict(含完整 children 子树),等价于 PageRouteSerializer.data。"""
    return {
        "id": route.id,
        "name": route.name,
        "path": route.path,
        "component": route.component,
        "parent": route.parent_id,
        "children": build_page_route_children(children_map, route.id),
    }
