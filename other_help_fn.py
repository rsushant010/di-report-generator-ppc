import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta, datetime
from dateutil import parser
import re
import requests
from io import BytesIO

owg_rw_keywords = ["Today net rejection (MT)","Overall wt gain (%)"], #
prod_key_col = [0,1,2,3,4]
prod_keywords = ["Abnormality (nos)"]
fl_keywords = ["Prod Loss (pcs)","Solution","Breakdown (minutes)"] , #
fl_key_col = [0,1,2,3] # key columns
cl_keywords = ["Breakdown"] , # key columns
cl_key_col = [0,1,2,3,4]
cf_keywords = ["Debtors not Discounted >25 days","Bad Debt","EMD/SD Due"]
rj_keywords = [0,1,2] #col no
lwg_keywords = [3,4,5] # col no
new_columns = ["Particulars" ,"Standard", "Actual","Solution","Date"]


def build_final_dataframe(dfs, filters, new_columns):
    """
    Apply filter_dataframe on multiple dataframes with given filter rules,
    then keep only first 5 columns and concatenate results.

    Parameters:
        dfs (dict): Dictionary of dataframes.
        filters (list): List of tuples -> (df_key, col_idx, ref_val, condition, values).
        new_columns (list): Column names for final dataframe.

    Returns:
        pd.DataFrame: Final concatenated dataframe sorted by Date and with index starting from 1.
    """
    df_list = []
    for df_key, col_idx, ref_val, condition, values in filters:
        filtered = filter_dataframe(dfs[df_key], col_idx, ref_val, condition, values)
        df_list.append(pd.DataFrame(filtered.values[:, :5], columns=new_columns))

    final_df = pd.concat(df_list, ignore_index=True)

    # ✅ Sort by "Date" column (ascending)
    if "Date" in final_df.columns:
        final_df = final_df.sort_values(by="Date", ascending=True, kind='mergesort')

    # Reset index to start from 1
    final_df.reset_index(drop=True, inplace=True)
    final_df.index = final_df.index + 1

    return final_df




def filter_dataframe(df, col_index, condition_value, condition_type, return_cols=None):
    """
    Filters a DataFrame based on numeric values extracted from a given column,
    and returns selected columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe
    col_index : int
        Index of the column on which condition is applied
    condition_value : int/float
        Value to compare with
    condition_type : str
        'less' or 'greater'
    return_cols : list, int, or str (optional)
        Columns to return.
        - If None: returns all columns
        - If list of ints: returns those column indices
        - If int: returns single column index
        - If str like '3:6': returns a slice of columns from index 3 to 6 (exclusive)
        - If str like '1,2,3,4,-1': returns comma-separated column indices

    Returns
    -------
    pd.DataFrame
        Filtered DataFrame with selected columns
    """

    # Select column by index
    col_name = df.columns[col_index]

    # Extract numeric values from that column
    numeric_series = (
        df[col_name]
        .astype(str)
        .str.extract(r'([-+]?\d*\.?\d+)')[0]  # extract first number
        .astype(float)
    )

    # Apply condition
    if condition_type == "less":
        mask = numeric_series < condition_value
    elif condition_type == "greater":
        mask = numeric_series > condition_value
    else:
        raise ValueError("condition_type must be 'less' or 'greater'")

    filtered_df = df[mask]

    # Handle return_cols
    if return_cols is None:
        return filtered_df
    elif isinstance(return_cols, str):
        if ":" in return_cols:
            # Handle range format like '3:6'
            start, end = map(int, return_cols.split(":"))
            return filtered_df.iloc[:, start:end]
        elif "," in return_cols:
            # Handle comma-separated format like '1,2,3,4,-1'
            try:
                col_indices = [int(x.strip()) for x in return_cols.split(",")]
                return filtered_df.iloc[:, col_indices]
            except ValueError:
                raise ValueError("Invalid comma-separated column indices. Use format like '1,2,3,4,-1'")
        else:
            # Single column index as string
            try:
                col_index = int(return_cols)
                return filtered_df.iloc[:, [col_index]]
            except ValueError:
                raise ValueError("Invalid column specification. Use int, list, range '3:6', or comma-separated '1,2,3,-1'")
    elif isinstance(return_cols, list):
        return filtered_df.iloc[:, return_cols]
    elif isinstance(return_cols, int):  # single index
        return filtered_df.iloc[:, [return_cols]]
    else:
        raise ValueError("return_cols must be None, list of indices, int, range string '3:6', or comma-separated string '1,2,3,-1'")




def string_to_date(date_string):
    try:
        dt = parser.parse(date_string, fuzzy=True, dayfirst=True)
        return dt.date()
    except (ValueError, OverflowError):
        return None



def find_indices(df, keyword, start=1):
    """Return list of index positions where keyword appears in df.index."""
    keyword = str(keyword).lower()
    return [
        idx
        for idx, name in enumerate(df.index, start=start)
        if keyword in str(name).lower().strip()
    ]


def find_col_index(row, keywords):
    """
    Given a pandas Series or Index `row` and a list of keywords (strings or lists of strings),
    returns a flat list of column indices where any keyword appears,
    preserving the order of keywords.
    """
    row_vals = [str(val).lower() for val in row]
    indices = []
    for kw in keywords:
        if isinstance(kw, list):  # multiple possible matches for one position
            kw_lower_list = [str(k).lower() for k in kw]
            kw_indices = [idx for idx, val in enumerate(row_vals) if any(k in val for k in kw_lower_list)]
        else:  # single keyword
            kw_lower = str(kw).lower()
            kw_indices = [idx for idx, val in enumerate(row_vals) if kw_lower in val]
        indices.extend(kw_indices)
    return indices



def append_word_if_missing(series, word_variants):
    """
    Append a word (or its variants) to each value in the given pandas Series
    if none of the variants are already present (case-insensitive),
    skipping NaN or empty values.
    """
    def process_cell(x):
        if pd.isna(x) or str(x).strip() == "":
            return ""
        text_lower = str(x).lower()
        # Check if any variant is already in the text
        if any(w.lower() in text_lower for w in word_variants):
            return x
        return str(x) + " " + word_variants[0]  # Append first variant by default

    return series.apply(process_cell)



def replace_empty_like_values(df):
    """
    Replace 0, NaN, None, 'nil', 'null', 'NaN', 'nan', and similar values with an empty string "" in the given DataFrame.
    """
    empty_like_values = [0, "0", "nil", "Nil", "NIL", "null", "Null", "NULL", "NaN", "nan", "NA", "na", None, np.nan]
    return df.replace(empty_like_values, "")



def format_decimals_as_percent(series):
    """Convert decimal numbers in a Series to percentage strings (first two digits only)."""
    def process_cell(x):
        try:
            if pd.isna(x):
                return ""
            num = float(x) * 100
            # Take integer part and keep only first two digits
            return f"{str(int(num))[:2]}%"
        except (ValueError, TypeError):
            return x  # leave non-numeric values as is

    return series.apply(process_cell)



def add_str_if_not_empty(series, text, position="after", empty_values=None):
    """
    Adds a string before or after each value in a Pandas Series
    if the value is not in empty_values or NaN.

    Parameters:
        series (pd.Series): The column data.
        text (str): String to add.
        position (str): "before" or "after".
        empty_values (list): Values to treat as empty.
    """
    if empty_values is None:
        empty_values = ["", "nan", "NaN", "None", "nil", "0"]

    def process(val):
        if pd.isna(val) or str(val).strip() in empty_values:
            return ""
        val_str = str(val)
        return f"{text}{val_str}" if position == "before" else f"{val_str}{text}"

    return series.apply(process)


