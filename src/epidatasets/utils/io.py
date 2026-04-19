"""I/O utilities for data export and merging."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def merge_dataframes(
    df_list: list[pd.DataFrame],
    on: Optional[list[str]] = None,
    how: str = "outer",
) -> pd.DataFrame:
    """Safely merge multiple DataFrames.

    Parameters
    ----------
    df_list : list of pd.DataFrame
        DataFrames to merge.
    on : list of str, optional
        Columns to merge on.
    how : str
        Merge type (``"outer"``, ``"inner"``, ``"left"``, ``"right"``).

    Returns
    -------
    pd.DataFrame
        Merged DataFrame.
    """
    if not df_list:
        return pd.DataFrame()

    if len(df_list) == 1:
        return df_list[0]

    result = df_list[0]
    for df in df_list[1:]:
        if on:
            result = result.merge(df, on=on, how=how, suffixes=("", "_dup"))
        else:
            result = result.merge(
                df, left_index=True, right_index=True, how=how
            )

    return result


def save_to_multiple_formats(
    df: pd.DataFrame,
    base_path: str,
    formats: Optional[list[str]] = None,
) -> dict[str, Path]:
    """Save a DataFrame to multiple file formats.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to save.
    base_path : str
        Base file path (without extension).
    formats : list of str, optional
        Formats to save (``"csv"``, ``"parquet"``, ``"json"``, ``"xlsx"``).

    Returns
    -------
    dict[str, Path]
        Mapping of format to saved file path.
    """
    if formats is None:
        formats = ["csv", "parquet"]

    base = Path(base_path)
    saved_paths: dict[str, Path] = {}

    for fmt in formats:
        if fmt == "csv":
            path = base.with_suffix(".csv")
            df.to_csv(path, index=False)
            saved_paths["csv"] = path

        elif fmt == "parquet":
            path = base.with_suffix(".parquet")
            df.to_parquet(path, index=False)
            saved_paths["parquet"] = path

        elif fmt == "json":
            path = base.with_suffix(".json")
            df.to_json(path, orient="records", indent=2)
            saved_paths["json"] = path

        elif fmt == "xlsx":
            path = base.with_suffix(".xlsx")
            df.to_excel(path, index=False)
            saved_paths["xlsx"] = path

    return saved_paths
