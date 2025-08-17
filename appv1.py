import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta, datetime
from dateutil import parser
import re
import requests
from io import BytesIO
from backend_p_f_d import process_for_date
from other_help_fn import filter_dataframe, string_to_date,find_indices,find_col_index,append_word_if_missing,replace_empty_like_values,format_decimals_as_percent,add_str_if_not_empty,build_final_dataframe


# --- Helper Functions from your Notebook ---

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


# --- Page Configuration ---
st.set_page_config(page_title="DI Report Generator", layout="wide")

# --- CUSTOM CSS TO REDUCE PADDING ---
# This injects CSS to reduce the top padding of the main block, making the UI more compact.
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
            padding-left: 5rem;
            padding-right: 5rem;
        }
    </style>
""", unsafe_allow_html=True)


# --- Initialize Session State ---
if 'intro_expanded' not in st.session_state:
    st.session_state.intro_expanded = True

# --- Dynamic Title ---
if 'processed_data' in st.session_state:
    st.title("📊 DI Report is Ready! ✅")
else:
    st.title("📊 DI Report Generator")

# --- Introduction Expander ---
with st.expander("👋 How to use this app", expanded=st.session_state.intro_expanded):
    st.markdown(
        """
        Welcome! This app automates DI production reports.
        **1. Upload**: Add your Excel file.
        **2. Select Dates**: Pick a single day or a date range.
        **3. Generate & Download**: Click to process and a download button will appear.
        """
    )

# --- Main UI in Columns ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("**📂 1. Upload Data**") # Using markdown instead of header for compactness
    uploaded_file = st.file_uploader(
        "Upload your DI Dashboard Excel file",
        type=["xlsx"],
        label_visibility="collapsed"
    )


with col2:
    st.markdown("**📅 2. Select Date(s)**")  # Using markdown instead of header
    report_type = st.radio("Report Type", ["Single Day", "Date Range"], horizontal=True)

    if report_type == "Date Range":
        c1, c2 = st.columns(2)
        with c1:
            date_start = st.date_input("Start Date", datetime.now().date())
        with c2:
            date_end = st.date_input("End Date", datetime.now().date())

        # ✅ Validation
        if date_end < date_start:
            st.error("⚠️ Please select a valid date range (End Date must be after Start Date).")
            st.error(
                f"⚠️ You selected the date range {date_start.strftime('%d-%m-%Y')} to {date_end.strftime('%d-%m-%Y')}."
            )


    else:  # Single Day
        date_start = st.date_input("Select Date", datetime.now().date())
        date_end = date_start



# --- Action Buttons ---
btn_col1, btn_col2 = st.columns(2)

with btn_col1:
    process_button = st.button("🚀 Generate Report", type="primary", use_container_width=True)

# with btn_col2:
#     if 'processed_data' in st.session_state:
#         output = BytesIO()
#         with pd.ExcelWriter(output, engine='openpyxl') as writer:
#             for sheet_name, df in st.session_state['processed_data'].items():
#                 df.to_excel(writer, sheet_name=sheet_name, index=True)

#         st.download_button(
#             label="📥 Download Excel Report",
#             data=output.getvalue(),
#             file_name=st.session_state.get('file_name', 'DI_Report.xlsx'),
#             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#             use_container_width=True
#         )



# Check if data exists
# if 'processed_data' in st.session_state:
#     sheet_name_to_download = "Summary"  # Change this to the sheet you want

#     if sheet_name_to_download in st.session_state['processed_data']:
#         output = BytesIO()
#         with pd.ExcelWriter(output, engine='openpyxl') as writer:
#             # Write only the selected sheet
#             st.session_state['processed_data'][sheet_name_to_download].to_excel(
#                 writer, sheet_name=sheet_name_to_download, index=True
#             )

#         st.download_button(
#             label=f"📥 Download '{sheet_name_to_download}' Sheet",
#             data=output.getvalue(),
#             file_name=f"{sheet_name_to_download}.xlsx",
#             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#             use_container_width=True
#         )
#     else:
#         st.warning(f"Sheet '{sheet_name_to_download}' not found in processed data.")


with btn_col2:
    if 'processed_data' in st.session_state:
        # Create 2 columns for side-by-side buttons
        col1, col2 = st.columns(2)

        # --- Button 1: Download All Reports ---
        with col1:
            output_all = BytesIO()
            with pd.ExcelWriter(output_all, engine='openpyxl') as writer:
                for sheet_name, df in st.session_state['processed_data'].items():
                    df.to_excel(writer, sheet_name=sheet_name, index=True)

            st.download_button(
                label="📥 Download All Reports",
                data=output_all.getvalue(),
                file_name=st.session_state.get('file_name', 'DI_Report.xlsx'),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        # --- Button 2: Download Analysis Report (final_df / Summary only) ---
        with col2:
            sheet_name_to_download = "Summary"  # Sheet to download
            if sheet_name_to_download in st.session_state['processed_data']:
                output_summary = BytesIO()
                with pd.ExcelWriter(output_summary, engine='openpyxl') as writer:
                    st.session_state['processed_data'][sheet_name_to_download].to_excel(
                        writer, sheet_name=sheet_name_to_download, index=True
                    )

                # --- Compute dynamic file name based on selected dates ---
                if date_start == date_end:
                    file_date = date_start.strftime('%d-%m-%Y')                   
                    file_name = f"Di Dashboard ({file_date}) Analysis Points.xlsx"
                else:
                    file_d_start = date_start.strftime('%d-%m-%Y')
                    file_d_end = date_end.strftime('%d-%m-%Y')
                    file_name = f"Di Dashboard ({file_d_start}_to_{file_d_end}) Analysis Points.xlsx"

                # --- Download button ---
                st.download_button(
                    label="📥 Download Analysis Report",
                    data=output_summary.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )



# --- Main App Logic (No changes needed here) ---
if process_button:
    st.session_state.intro_expanded = False
    if not uploaded_file:
        st.error("❗ Please upload a file to begin.")
    else:
        # (The rest of your processing logic remains unchanged)
        with st.spinner("Processing... This may take a moment. ⏳"):
            try:
                xls = pd.ExcelFile(uploaded_file)
                sheet_map = {string_to_date(s): s for s in xls.sheet_names if string_to_date(s) is not None}
                prod_list, rj_list, lwg_list, owg_list, fl_list, cl_list, cf_list = ([] for _ in range(7))

                start_date = date_start
                end_date = date_end

                current_date = start_date
                while current_date <= end_date:
                    sheet_name = sheet_map.get(current_date)
                    if sheet_name:
                        st.toast(f"Processing: {current_date.strftime('%d %b')}...", icon="✅")
                        sheet_df = pd.read_excel(xls, sheet_name=sheet_name)
                        results = process_for_date(sheet_name, sheet_df)
                        prod_list.append(results[0]); rj_list.append(results[1]); lwg_list.append(results[2]); owg_list.append(results[3]); fl_list.append(results[4]); cl_list.append(results[5]); cf_list.append(results[6])
                    else:
                        st.warning(f"⏩ Skipping {current_date.strftime('%d %b')} (sheet not found)")
                    current_date += timedelta(days=1)

                if not prod_list:
                    st.error("No data found for the selected date range.")
                else:
                    cum_prod_db = pd.concat(prod_list); cum_rj_db = pd.concat(rj_list); cum_lwg_db = pd.concat(lwg_list); cum_owg_db = pd.concat(owg_list); cum_fl_db = pd.concat(fl_list); cum_cl_db = pd.concat(cl_list); cum_cf_db = pd.concat(cf_list)
                    dfs = { "prod": cum_prod_db, "rj": cum_rj_db, "lwg": cum_lwg_db, "owg": cum_owg_db, "fl": cum_fl_db, "cl": cum_cl_db }
                    filters = [
                         ("prod", 3, 0, "greater", "6,7,8,9,-1"), ("prod", 5, 9, "greater", "10,11,12,13,14"),
                         ("rj",   2, 4, "greater", "3,4,5,6,-1"), ("lwg",  2, 17, "less",    "3:8"),
                         ("owg",  1, 17, "less",    "2,3,4,5,-1"), ("owg",  0, 17, "greater", "6,7,8,9,-1"),
                         ("fl",   4, 9, "greater", "7,8,9,10,-1"), ("fl",   6, 0, "greater", "11,12,13,14,-1"),
                         ("cl",   5, 0, "greater", "6,7,8,9,-1"),
                    ]
                    
                    final_df = build_final_dataframe(dfs, filters, new_columns)
                    if date_start == date_end:
                        final_df = final_df = final_df.iloc[:, :-1]

                     
                    

                    st.success("🎉 Processing Complete! Your report is ready for download.")
                    st.session_state['processed_data'] = {
                        "Production": cum_prod_db, "Highest_rej": cum_rj_db,
                        "Lowest_wg": cum_lwg_db, "Overall_wg_rw": cum_owg_db,
                        "FL_db": cum_fl_db, "CL_db": cum_cl_db, "CF_db": cum_cf_db,
                        "Summary": final_df
                    }
                    # --- Generate filename based on date selection ---
                if date_start == date_end:
                    # Format for a single day report
                    formatted_date = date_start.strftime('%d-%m-%Y')                   
                    file_name = f"Di Dashboard ({formatted_date}) Analysis Points.xlsx"
                else:
                    # Format for a date range report
                    formatted_start = date_start.strftime('%d-%m-%Y')
                    formatted_end = date_end.strftime('%d-%m-%Y')
                    file_name = f"{formatted_start}_to_{formatted_end}_cum_di_report.xlsx"

                # Store the generated file name in the session state
                st.session_state['file_name'] = file_name
                st.rerun()
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.exception(e)
