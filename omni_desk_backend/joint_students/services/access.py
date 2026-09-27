"""联培生数据可见性规则（HTTP 接口与 AI 工具共用）。

- 联培生管理员组成员 / superuser：全部联培生；
- 导师（含"联培生导师"组）：自己名下的联培生；
- 其他用户：本人对应的联培生记录。
"""

from __future__ import annotations

from joint_students.models import JointStudent
from joint_students.permissions import MANAGER_GROUP, user_is_mentor


def own_joint_student_ids(user) -> list[int]:
    """返回该 user 名下 Personnel 关联的 JointStudent id 列表。"""
    return list(JointStudent.objects.filter(personnel__user_account=user).values_list("id", flat=True))


def mentor_joint_student_ids(user) -> list[int]:
    """返回该 user 作为导师时名下的 JointStudent id 列表。"""
    return list(JointStudent.objects.filter(mentor__user_account=user).values_list("id", flat=True))


def can_see_all_students(user) -> bool:
    """联培生管理员 / superuser 可见全部联培生。"""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=MANAGER_GROUP).exists()


def visible_joint_students(user, qs=None):
    """按上述规则过滤联培生 QuerySet；未登录用户返回空集。"""
    if qs is None:
        qs = JointStudent.objects.all()
    if not user or not user.is_authenticated:
        return qs.none()
    if can_see_all_students(user):
        return qs
    scoped_ids = set(own_joint_student_ids(user))
    if user_is_mentor(user):
        scoped_ids |= set(mentor_joint_student_ids(user))
    return qs.filter(id__in=scoped_ids)
