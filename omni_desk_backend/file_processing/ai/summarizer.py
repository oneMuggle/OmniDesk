import pandas as pd


class DataSummarizer:
    """数据摘要生成器 - 为表格数据生成统计摘要信息"""

    def summarize_table(self, sheets_data: list[dict[str, any]]) -> dict[str, any]:
        """生成表格数据摘要

        Args:
            sheets_data: 包含多个 sheet 数据的列表，每个 sheet 是包含
                         name, headers, data 的字典

        Returns:
            包含 sheet_count, total_rows, summaries 的摘要字典
        """
        summaries = []

        for sheet in sheets_data:
            df = pd.DataFrame(sheet["data"], columns=sheet["headers"])

            summary = {
                "sheet_name": sheet["name"],
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": [],
            }

            # 分析每一列
            for col in df.columns:
                col_info = {
                    "name": col,
                    "type": str(df[col].dtype),
                    "null_count": int(df[col].isnull().sum()),
                    "unique_count": int(df[col].nunique()),
                }

                # 数值列统计
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_info.update(
                        {
                            "min": float(df[col].min()) if not df[col].empty else None,
                            "max": float(df[col].max()) if not df[col].empty else None,
                            "mean": float(df[col].mean()) if not df[col].empty else None,
                            "sum": float(df[col].sum()) if not df[col].empty else None,
                        }
                    )

                summary["columns"].append(col_info)

            summaries.append(summary)

        return {
            "sheet_count": len(sheets_data),
            "total_rows": sum(s["row_count"] for s in summaries),
            "summaries": summaries,
        }
