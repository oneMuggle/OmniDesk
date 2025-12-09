# 文档整理最终执行计划

## 1. 目标

对 `docs/` 文件夹进行结构性优化，合并内容相近或重复的文档，删除过时和多余的文件，以提高文档库的可维护性和清晰度。

## 2. 合并方案

以下文档将被合并，并以新的“总体规划”文档取代：

| 主题 | 新的总体规划文档 | 被合并的源文档 |
| :--- | :--- | :--- |
| **项目资料管理** | `docs/项目资料智能管理功能实现计划.md` | `docs/项目资料智能管理功能实现详细计划.md` |
| **公告功能** | `docs/announcement_feature_plan.md` | `docs/announcement_richtext_plan.md` |
| **日历样式** | `docs/calendar_style_optimization_plan.md` | `docs/calendar_beautification_plan.md` |
| **排班系统** | `docs/schedule_system_master_plan.md` | `schedule_display_bugfix_plan.md`, `schedule_drag_and_drop_plan.md`, `schedule_management_bugfix_plan.md`, `schedule_personnel_fix_plan.md`, `schedule_refactoring_plan.md`, `schedule_sequence_bugfix_plan.md`, `schedule_sequence_plan.md`, `schedule_simplification_plan.md`, `schedule_workday_holiday_split_plan.md` |
| **管理面板** | `docs/admin_panel_master_plan.md` | `admin_page_reconstruction_plan.md`, `admin_panel_management_page_plan.md`, `admin_sidebar_style_plan.md`, `sidebar_permission_plan.md`, `sidebar_padding_fix_plan.md` |
| **用户系统** | `docs/user_system_master_plan.md` | `user_communication_module_plan.md`, `user_group_and_permissions_design.md`, `user_permission_layout_plan.md`, `user_personnel_association_plan.md` |

## 3. 删除列表

在完成上述合并后，以下所有源文档以及其他被判定为过时的文件将被删除：

*   `docs/项目资料智能管理功能实现详细计划.md`
*   `docs/announcement_richtext_plan.md`
*   `docs/calendar_beautification_plan.md`
*   `docs/schedule_display_bugfix_plan.md`
*   `docs/schedule_drag_and_drop_plan.md`
*   `docs/schedule_management_bugfix_plan.md`
*   `docs/schedule_personnel_fix_plan.md`
*   `docs/schedule_refactoring_plan.md`
*   `docs/schedule_sequence_bugfix_plan.md`
*   `docs/schedule_sequence_plan.md`
*   `docs/schedule_simplification_plan.md`
*   `docs/schedule_workday_holiday_split_plan.md`
*   `docs/admin_page_reconstruction_plan.md`
*   `docs/admin_panel_management_page_plan.md`
*   `docs/admin_sidebar_style_plan.md`
*   `docs/sidebar_padding_fix_plan.md`
*   `docs/sidebar_permission_plan.md`
*   `docs/user_communication_module_plan.md`
*   `docs/user_group_and_permissions_design.md`
*   `docs/user_permission_layout_plan.md`
*   `docs/user_personnel_association_plan.md`
*   `docs/计划.md` (已过时)

## 4. 执行步骤

1.  **确认**: 用户审查并批准此计划。
2.  **执行**: 切换到 `code` 模式。
3.  **操作**:
    *   执行文件写入操作，以确保所有合并内容已保存到新的总体规划文档中。
    *   执行 `del` (或 `rm`) 命令，删除上述列表中的所有文件。
4.  **完成**: 提交最终的操作摘要。