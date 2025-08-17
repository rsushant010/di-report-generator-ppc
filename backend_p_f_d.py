import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta, datetime
from dateutil import parser
import re
import requests
from io import BytesIO

from other_help_fn import filter_dataframe, string_to_date, find_indices, find_col_index, append_word_if_missing, replace_empty_like_values, format_decimals_as_percent, add_str_if_not_empty,build_final_dataframe

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



def process_for_date(date, df_raw):
    # Standardize index & columns
    df_raw.columns = df_raw.iloc[3]
    df_raw = df_raw.iloc[4:].reset_index(drop=True)
    df_raw.set_index(df_raw.columns[0], inplace=True)
    df_raw.index = df_raw.index.astype(str).str.replace("\xa0", " ", regex=False).str.strip().str.upper()

    # Pre-slice di_db
    columns_to_keep = [0, 1, 2, 3, 4, -2]
    di_db = df_raw.iloc[:, columns_to_keep]

    # Find key indices (cached variables)
    total_indices = find_indices(df_raw, "total")
    unit_indices = find_indices(df_raw, "unit")
    cf_indices = find_indices(df_raw, "customer finance")

    di_db_1_total_index, di_db_2_total_index, fl_total_index, cl_total_index, cf_total_index = (
        total_indices[0], total_indices[1], total_indices[2], total_indices[3], total_indices[-2]
    )
    di_db_2_unit_index, fl_unit_index, cl_unit_index = unit_indices[0], unit_indices[1], unit_indices[2]
    cf_db_index = cf_indices[0]

    # Column dictionaries
    prod_dict   = find_col_index(df_raw.columns, prod_keywords)
    owg_rw_dict = find_col_index(df_raw.iloc[di_db_2_unit_index-1], owg_rw_keywords)
    fl_dict     = find_col_index(df_raw.iloc[fl_unit_index-1], fl_keywords)
    cl_dict     = find_col_index(df_raw.iloc[cl_unit_index-1], cl_keywords)
    cf_dict     = find_col_index(df_raw.iloc[cf_db_index], cf_keywords)

    # Production DB
    prod_db = df_raw.iloc[:di_db_1_total_index, prod_key_col + prod_dict]
    prod_db = replace_empty_like_values(prod_db)
    # prod_db.index = prod_db.index.to_series().ffill()
    prod_db["index_loss"] = prod_db.index.astype(str)
    prod_db.iloc[:,3] = append_word_if_missing(prod_db.iloc[:,3],["MT"])
    prod_db.iloc[:,5] = append_word_if_missing(prod_db.iloc[:,5],["Nos"])

    prod_db["Standard_loss"] = "0 MT"
    prod_db["actual"] = prod_db.iloc[:,3]
    prod_db["loss_description"] = prod_db.apply(
    lambda row: (
        "Production Loss is " + str(row.iloc[3])+"." + "\n"+ str(row.iloc[4])
        if str(row.iloc[3]).strip() not in ["", "nan", "NaN", "0"] or
           str(row.iloc[4]).strip() not in ["", "nan", "NaN", "0"]
        else ""
    ),
    axis=1
    )


    prod_db["index_abnor"] = prod_db.index.astype(str)
    prod_db["standard_abnormality"] = "<10 nos"
    prod_db["actual_abnormality"] = prod_db.iloc[:,5]
    # prod_db["abnormality_description"] = prod_db.iloc[:, 5].astype(str) + " of abnormality."
    prod_db["abnormality_description"] = add_str_if_not_empty(prod_db.iloc[:, 5]," of abnormality.","after")


    # Rejection DB
    rj_db = df_raw.iloc[di_db_2_unit_index:di_db_2_total_index, rj_keywords]
    rj_db.columns = df_raw.iloc[di_db_2_unit_index-1, rj_keywords]
    rj_db = replace_empty_like_values(rj_db)
    rj_db.iloc[:,2] = format_decimals_as_percent(rj_db.iloc[:,2])
    rj_db["u_c_d"] = rj_db.index + " " + rj_db.iloc[:, 0].astype(str).str.upper() + " " + rj_db.iloc[:, 1].astype(str)
    rj_db["standard"] = "<5%"
    rj_db["actual_rj"] = rj_db.iloc[:,2]
    # rj_db["description"] = rj_db.iloc[:,2].astype(str) + "% Highest rejection."
    rj_db["description"] = add_str_if_not_empty(rj_db.iloc[:,2]," Highest rejection.","after")


    # Lowest weight gain DB
    lwg_db = df_raw.iloc[di_db_2_unit_index:di_db_2_total_index, lwg_keywords]
    lwg_db.columns = df_raw.iloc[di_db_2_unit_index-1, lwg_keywords]
    lwg_db = replace_empty_like_values(lwg_db)
    lwg_db.iloc[:,2] = format_decimals_as_percent(lwg_db.iloc[:,2])
    lwg_db["u_c_d"] = lwg_db.index + " " + lwg_db.iloc[:, 0].astype(str).str.upper() + " " + lwg_db.iloc[:, 1].astype(str).str.upper()

    lwg_db["Standard"] = ">16%"
    lwg_db["actual_lwg"] = lwg_db.iloc[:,2]
    # lwg_db["description"] =  lwg_db.iloc[:,2] + "% Lowest Weight Gain."
    lwg_db["description"] = add_str_if_not_empty(lwg_db.iloc[:,2]," Lowest Weight Gain.","after")


    # Overall weight gain DB
    owg_db = df_raw.iloc[di_db_2_unit_index:di_db_2_total_index, owg_rw_dict]
    owg_db.columns = df_raw.iloc[di_db_2_unit_index-1, owg_rw_dict]
    owg_db = replace_empty_like_values(owg_db)
    owg_db.iloc[:,0] = append_word_if_missing(owg_db.iloc[:,0],["MT"])
    owg_db.iloc[:,1] = format_decimals_as_percent(owg_db.iloc[:,1])

    owg_db["index_wg"] = owg_db.index.astype(str)
    # owg_db = format_decimals_as_percent(owg_db.iloc[:,1])
    owg_db["standard wg"] = ">16%"
    owg_db["actual_wg"] = owg_db.iloc[:,1]
    # owg_db["description_owg"] = (
    #     pd.to_numeric(owg_db.iloc[:, 1].astype(str).str.replace("\xa0", "", regex=False).str.strip(), errors="coerce")
    #     .fillna(0) * 100
    # ).astype(int).astype(str) + "% Overall Weight Gain."
    owg_db["description_owg"] = add_str_if_not_empty(owg_db.iloc[:,1]," Overall Weight Gain.","after")

    owg_db["index_rw"] = owg_db.index.astype(str)
    # Using position (row 0, column "index_rw")
    owg_db.iloc[0, 6] = "MAIN SDP1 SDP2 SDP3 SDP4 SDP5"

    owg_db["standard rw"] = "0 MT"
    owg_db["actual_rw"] = owg_db.iloc[:,0]
    # owg_db["description_rw"] = owg_db.iloc[:, 0].astype(str) + " MT Net Rejection."
    owg_db["description_rw"] = add_str_if_not_empty(owg_db.iloc[:,0]," Net Rejection.","after")

    # Finishing line DB
    fl_db = df_raw.iloc[fl_unit_index:fl_total_index, fl_key_col + fl_dict]
    fl_db.columns = df_raw.iloc[fl_unit_index-1, fl_key_col + fl_dict]
    fl_db = replace_empty_like_values(fl_db)
    col0 = fl_db.iloc[:, 0].astype(str).str.upper()
    col2 = fl_db.iloc[:, 2].astype(str).str.upper()
    fl_db.iloc[:,4] = append_word_if_missing(fl_db.iloc[:,4],["Pcs"])
    fl_db.iloc[:,6] = append_word_if_missing(fl_db.iloc[:,6],["Mins"])

    fl_db["unit_dia"] = np.where(
        fl_db.iloc[:, 0].notna() & (col2.str.strip() != ""),
        fl_db.index + " " + col0,
        fl_db.index + " " + col2
    )
    fl_db["standard"] = "<10 pcs"
    fl_db["actual"] = fl_db.iloc[:,4]

    fl_db["description_rw"] = add_str_if_not_empty(fl_db.iloc[:, 4],"Production loss ","before").astype(str) + ". " + fl_db.iloc[:, 5].astype(str)
    # fl_db["pd_loss_description"] = "Production loss " + fl_db.iloc[:, 4].astype(str) + " Pcs. " + fl_db.iloc[:, 5].astype(str)

    fl_db["unit_dia_bd"] = fl_db["unit_dia"]
    fl_db["standard_bd"] ="0 Mins"
    fl_db["actual_bd"] = fl_db.iloc[:,6]
    # fl_db["bd_description"] = "Breakdown for " + fl_db.iloc[:, 6].astype(str) + " Mins."
    fl_db["bd_description"] = add_str_if_not_empty(fl_db.iloc[:, 6],"Breakdown for ","before")
    fl_db["bd_description"] = fl_db["bd_description"].astype(str) + "."

    # Coating line DB
    cl_db = df_raw.iloc[cl_unit_index:cl_total_index, cl_key_col + cl_dict]
    cl_db.columns = df_raw.iloc[cl_unit_index-1, cl_key_col + cl_dict]
    cl_db = replace_empty_like_values(cl_db)

    # cl_db.iloc[:,5] = append_word_if_missing(cl_db.iloc[:,5],"Mins")
    cl_db.iloc[:, 5] = cl_db.iloc[:, 5].apply(
    lambda x: (
        re.search(r'\d+', str(x)).group() + " Mins"
        if pd.notna(x) and re.search(r'\d+', str(x))
        else ""
        )
    )

    cl_db["u_d"] = cl_db.index + " " + cl_db.iloc[:, 0].astype(str)
    cl_db["standard_bd"] ="0 Mins"
    cl_db["actual_bd"] = cl_db.iloc[:,5]
    cl_db["bd_description"] = add_str_if_not_empty(cl_db.iloc[:, 5],"Breakdown for ","before")
    cl_db["bd_description"] = cl_db["bd_description"].astype(str) + "."
    # cl_db["bd_description"] = "Breakdown for " + cl_db.iloc[:, 5].astype(str)

    # Customer finance DB
    cf_db = df_raw.iloc[[cf_total_index-1], cf_dict]
    cf_db.columns = df_raw.iloc[cf_db_index, cf_dict]
    cf_db["d_n_d"] = cf_db.iloc[:,0].astype(str) + " Debtors not Discounted >25 days."
    cf_db["bad_debt_des"] = cf_db.iloc[:,1].astype(str) + " Nos Bad debt."
    cf_db["e_s_d"] = cf_db.iloc[:,2].astype(str) + " EMD/SD due."


    # Add date column to all
    for df in (prod_db, rj_db, lwg_db, owg_db, fl_db, cl_db, cf_db):
        df["date"] = date

    return prod_db, rj_db, lwg_db, owg_db, fl_db, cl_db, cf_db


