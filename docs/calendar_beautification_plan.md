# 日历界面美化计划

## 目标
美化日历的整体布局和配色，使其更现代、更简洁。

## 初步分析和美化方向

1.  **文件定位：** `omni_desk_frontend/src/components/CalendarPage.css` 是日历页面的主要样式文件，包含了 `schedule-page`（整体页面背景）、`schedule-container`（日历容器）以及 FullCalendar (fc) 的核心样式。
2.  **现有配色：** 项目已使用 `var(--bg-color)` 和 `var(--text-color)` 等 CSS 变量，这为统一管理颜色提供了便利。事件（`fc-event-schedule`）使用了渐变色。
3.  **现有布局：** `schedule-container` 具有明显的阴影 (`box-shadow`) 和圆角 (`border-radius: 12px;`)。头部工具栏 (`fc-header-toolbar`) 也有背景色和圆角。
4.  **美化目标：**
    *   **配色：** 采用更柔和、专业的调色板。减少或简化渐变的使用，使其更平坦或更微妙。确保浅色和暗色模式下的配色方案和谐统一，并提供良好的可读性。
    *   **布局：** 调整阴影使其更轻盈，或考虑使用更细的边框来增加简洁感。优化内边距和外边距，使组件看起来更紧凑、现代。

## 详细计划步骤

1.  **定义核心 CSS 变量：**
    *   在 `CalendarPage.css` 或一个全局的样式文件中，定义一套新的颜色变量，例如：
        *   `--primary-color`（主色调，用于按钮、高亮等）
        *   `--secondary-color`（辅助色）
        *   `--background-light` / `--background-dark`（浅色/暗色背景）
        *   `--surface-light` / `--surface-dark`（卡片、容器背景）
        *   `--text-light` / `--text-dark`（浅色/暗色文本颜色）
        *   `--border-color`（边框颜色）
        *   `--shadow-color`（阴影颜色）
    *   确保这些变量可以在 `.dark` 类下进行切换，以实现暗黑模式。

2.  **美化 `schedule-page` 和 `schedule-container`：**
    *   **`schedule-page`：**
        *   将 `background` 渐变调整为更简洁的纯色或非常微妙的渐变，使用新的背景变量。
        *   ```css
            .schedule-page {
              background: var(--background-light); /* 或更现代的渐变 */
              /* ... 其他样式 ... */
            }
            .schedule-page.dark {
              background: var(--background-dark);
            }
            ```
    *   **`schedule-container`：**
        *   调整 `box-shadow` 为更轻、更现代的样式，例如 `box-shadow: 0 1px 3px 0 var(--shadow-color), 0 1px 2px -1px var(--shadow-color);`。
        *   `background: white;` 替换为 `background: var(--surface-light);`。
        *   `border-radius: 12px;` 可以保持或微调至 `8px` 或 `10px`。
        *   ```css
            .schedule-container {
              background: var(--surface-light);
              box-shadow: 0 1px 3px 0 var(--shadow-color), 0 1px 2px -1px var(--shadow-color);
              /* ... 其他样式 ... */
            }
            .schedule-container.dark {
              background: var(--surface-dark);
            }
            ```

3.  **优化 `fc-header-toolbar` (FullCalendar 头部工具栏)：**
    *   保持 `background: var(--bg-color);` 和 `border-radius: 8px;`，但可以微调 `padding`，使其更紧凑。
    *   确保在暗黑模式下，工具栏的背景色和按钮颜色与整体主题协调。

4.  **简化事件样式 (`fc-event-schedule`)：**
    *   将当前的 `linear-gradient` 背景替换为更平坦的颜色，或更柔和、对比度更低的渐变。
    *   **`fc-event-schedule-staff`：** 使用一个更柔和的蓝色系纯色或微渐变。
    *   **`fc-event-schedule-leader`：** 使用一个更柔和的橙色/黄色系纯色或微渐变。
    *   移除 `border: 1px solid white;` 或改为与事件背景色更协调的边框颜色。
    *   调整 `box-shadow` 为更轻的样式。
    *   ```css
        .fc-event-schedule-staff {
          background: var(--primary-color-light); /* 新定义的柔和蓝色 */
          border: none; /* 或 var(--border-color) */
          box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .fc-event-schedule-leader {
          background: var(--secondary-color-light); /* 新定义的柔和橙色 */
          border: none;
          box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        /* 暗黑模式下的事件颜色也需要相应调整 */
        .dark .fc-event-schedule-staff {
          background: var(--primary-color-dark);
        }
        .dark .fc-event-schedule-leader {
          background: var(--secondary-color-dark);
        }
        ```

5.  **日历单元格和文本：**
    *   确保 `fc` 的 `font-family` 和 `color` 使用 CSS 变量，并在暗黑模式下正确切换。
    *   检查日期单元格（如 `fc-daygrid-day`）的背景色、边框和文本颜色，使其与整体简洁风格一致。

6.  **响应式设计：**
    *   保留并检查现有媒体查询，确保美化后的样式在移动设备上依然表现良好。

## 计划流程图

```mermaid
graph TD
    A[开始日历美化任务] --> B{分析现有样式与用户需求};
    B --> C[读取 `CalendarPage.css`];
    C --> D[确定“现代、简洁”设计原则];
    D --> E[制定配色方案];
    E --> E1[定义新的CSS变量];
    E --> E2[调整 `schedule-page` 背景];
    E --> E3[优化 `schedule-container` 阴影和背景];
    E --> E4[简化事件颜色和边框];
    E --> E5[确保暗黑模式兼容性];
    D --> F[制定布局优化方案];
    F --> F1[调整头部工具栏间距];
    F --> F2[检查日历单元格样式];
    D --> G[确认响应式设计];
    G --> H[完成计划，等待用户确认];