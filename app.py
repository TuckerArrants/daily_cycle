import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, time
import plotly.express as px
import os, io, base64, requests

st.set_page_config(layout='wide')

#########################################
### Functions
#########################################

@st.cache_data
def load_data_for_instrument(instrument: str) -> pd.DataFrame:
    df = pd.read_csv(f'https://raw.githubusercontent.com/TuckerArrants/daily_cycle/main/{instrument}_Full_Day_Partial_Day_From_2008_V1.csv')
    return df

# ✅ Store username-password pairs
USER_CREDENTIALS = {
    "badboyz": "bangbang",
    "dreamteam" : "strike",
}


#########################################
### Log In
#########################################
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None

if not st.session_state["authenticated"]:
    st.title("Login to Database")

    # Username and password fields
    username = st.text_input("Username:")
    password = st.text_input("Password:", type="password")

    # Submit button
    if st.button("Login"):
        if username in USER_CREDENTIALS and password == USER_CREDENTIALS[username]:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username  # Store the username
            # ← Clear *all* @st.cache_data caches here:
            st.cache_data.clear()

            st.success(f"Welcome, {username}! Loading fresh data…")
            st.rerun()
        else:
            st.error("Incorrect username or password. Please try again.")

    # Stop execution if user is not authenticated
    st.stop()

# ✅ If authenticated, show the full app
st.title("Daily Cycles")

# ↓ in your sidebar:
instrument_options = ["ES", "NQ", "YM", "RTY", "CL", "GC"]
selected_instrument = st.sidebar.selectbox("Instrument", instrument_options)

#########################################
### Data Loading and Processing
#########################################
df = load_data_for_instrument(selected_instrument)

df['date'] = pd.to_datetime(df['session_date']).dt.date

rename_map = {'pre_adr' : 'Daily Open-ADR Transition',
              'adr' : 'ADR',
              'adr_transition' : 'ADR-ODR Transition',
              'odr' : 'ODR',
              'odr_transition' : 'ODR-RDR Transition',
              'rdr' : 'RDR',
              'untouched' : 'Untouched',
              'uxp' : 'UXP',
              'ux' : 'UX',
              'u' : 'U',
              'dxp' : 'DXP',
              'dx' : 'DX',
              'd' : 'D',
              'rx' : 'RX',
              'rc' : 'RC',
              'none' : 'None',
              'long' : 'Long',
              'short' : 'Short',   
              'box_formation' : 'Box Formation',
              'before_confirmation' : 'Before Confirmation',
              'after_confirmation' : 'After Confirmation',
} 

#df = df.replace(rename_map)

# 1) Make sure 'date' is a datetime column
if "date" in df.columns:
    df["date"] = pd.to_datetime(df["session_date"])
else:
    st.sidebar.warning("No 'date' column found in your data!")

#########################################
### Sidebar
#########################################
day_options = ['All'] + ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
selected_day = st.sidebar.selectbox("Day of Week", day_options, key="selected_day")

min_date = df["date"].min().date()
max_date = df["date"].max().date()
start_date, end_date = st.sidebar.date_input(
    "Select date range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    key="date_range"
)

#########################################
### Resets
#########################################
default_filters = {
    "selected_day":                       "All",
    "date_range":                 (min_date, max_date),

    
    "podr_to_rdr_model_filter" : [],
    "rdr_to_adr_model_filter" : [],
    "rdr_to_odr_model_filter": [],
    "adr_to_odr_model_filter" : [],
   
}

# 2) Reset button with callback
def reset_all_filters():
    for key, default in default_filters.items():
        # only touch keys that actually exist
        if key in st.session_state:
            st.session_state[key] = default

st.sidebar.button("Reset all filters", on_click=reset_all_filters)

if isinstance(start_date, tuple):
    # sometimes date_input returns a single date if you pass a single default
    start_date, end_date = start_date

#########################################
### Model Filters
#########################################
row1_cols = st.columns([1, 1, 1, 1])
with row1_cols[0]:
    podr_to_rdr_model_filter = st.multiselect(
        "PODR-RDR Model",
        options=["UXP", "UX", "U", "DXP", "DX", "D", "RC", "RX"],
        key="podr_to_rdr_model_filter",
    )
    
with row1_cols[1]:
    rdr_to_adr_model_filter = st.multiselect(
        "RDR-ADR Model",
        options=["UXP", "UX", "U", "DXP", "DX", "D", "RC", "RX"],
        key="rdr_to_adr_model_filter", 
    )   

with row1_cols[2]:
    rdr_to_odr_model_filter = st.multiselect(
        "RDR-ODR Model",
        options=["UXP", "UX", "U", "DXP", "DX", "D", "RC", "RX"],
        key="rdr_to_odr_model_filter",
    )
    
with row1_cols[3]:
    adr_to_odr_model_filter = st.multiselect(
        "ADR-ODR Model",
        options=["UXP", "UX", "U", "DXP", "DX", "D", "RC", "RX"],
        key="adr_to_odr_model_filter",
    )        

#########################################
### Filter Mapping
#########################################   

# map each filter to its column
inclusion_map = {

    "podr_to_rdr_model" : "podr_to_rdr_model_filter",
    "rdr_to_adr_model" : "rdr_to_adr_model_filter",
    "rdr_to_odr_model" : "rdr_to_odr_model_filter",
    "adr_to_odr_model" : "adr_to_odr_model_filter",

}

# Apply filters
df_filtered = df.copy()

sel_day = st.session_state["selected_day"]
if sel_day != "All":
    df_filtered = df_filtered[df_filtered["day_of_week"]  == sel_day]

# — Date range —
start_date, end_date = st.session_state["date_range"]
df_filtered = df_filtered[
    (df_filtered["date"] >= pd.to_datetime(start_date)) &
    (df_filtered["date"] <= pd.to_datetime(end_date))
]

for col, state_key in inclusion_map.items():
    sel = st.session_state[state_key]
    if isinstance(sel, list):
        if sel:  # non-empty list means “only these”
            df_filtered = df_filtered[df_filtered[col].isin(sel)]
    else:
        if sel != "All":
            df_filtered = df_filtered[df_filtered[col] == sel]

  
#########################################################
### Models Graphs
#########################################################
model_cols = [
    "podr_to_rdr_model",
    "rdr_to_adr_model",
    "rdr_to_odr_model",
    "adr_to_odr_model"]

model_titles = [
    "PODR-RDR Model",
    "RDR-ADR Model",
    "RDR-ODR Model",
    "ADR-ODR Model"]

row1 = st.columns(len(model_cols))
for idx, col in enumerate(model_cols):
    # 1) drop any actual None/NaN values so they never even show up
    series = df_filtered[col].dropna() 

    # 2) get normalized counts
    counts = series.value_counts(normalize=True)

    # 3) if you still have the string "None" in your index, drop it
    counts = counts.drop("None", errors="ignore")

    # 4) turn into percentages
    perc = counts * 100
    perc = perc[perc > 0]

    # now build the bar‐chart
    fig = px.bar(
        x=perc.index,
        y=perc.values,
        text=[f"{v:.1f}%" for v in perc.values],
        title=model_titles[idx],
        labels={"x": "", "y": ""},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis_tickangle=0,
        margin=dict(l=10,r=10,t=30,b=10),
        yaxis=dict(showticklabels=False))

    #row1[idx].plotly_chart(fig, use_container_width=True)



#########################################################
### Partial Day Highs/Lows 5m Buckets 
#########################################################
time_order = [f"{h:02d}:{m:02d}:00" for h in range(4, 10) for m in range(0, 60, 5) if not (h == 9 and m > 25)]

partial_day_high_col = [
    "partial_day_high_hm",
]
partial_day_type_title = [
    "Partial Day High",
]

partial_day_high_row = st.columns(1)
for idx, col in enumerate(partial_day_high_col):
    if col in df_filtered:
        counts = (
            df_filtered[col]
            .value_counts(normalize=True)
            .reindex(time_order, fill_value=0)
        )
        perc = counts * 100
        #perc = perc[perc > 0]

        fig = px.bar(
            x=perc.index,
            y=perc.values,
            text=[f"{v:.1f}%" for v in perc.values],
            labels={"x": "", "y": ""},
            title=partial_day_type_title[idx],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_tickangle=90,
            xaxis={"categoryorder": "array", "categoryarray": list(perc.index)},
            margin=dict(l=10, r=10, t=30, b=10),
        )

        partial_day_high_row[idx].plotly_chart(fig, use_container_width=True)
        
#####################################
### Partial Day Type
#####################################
partial_day_type_cols = [
    "partial_day_type",
]
partial_day_type_title = [
    "Partial Day Type",
]
segment_order_with_no = ["Upside", "Downside", "Inside", "Outside", "Undefined"]

partial_day_type_row = st.columns(1)
for idx, col in enumerate(partial_day_type_cols):
    if col in df_filtered:
        counts = (
            df_filtered[col]
            .value_counts(normalize=True)
            .reindex(segment_order_with_no, fill_value=0)
        )
        perc = counts * 100
        perc = perc[perc > 0]

        fig = px.bar(
            x=perc.index,
            y=perc.values,
            text=[f"{v:.1f}%" for v in perc.values],
            labels={"x": "", "y": ""},
            title=partial_day_type_title[idx],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_tickangle=90,
            yaxis=dict(showticklabels=False),
            xaxis={"categoryorder": "array", "categoryarray": list(perc.index)},
            margin=dict(l=10, r=10, t=30, b=10),
        )

        partial_day_type_row[idx].plotly_chart(fig, use_container_width=True)

#####################################
### Day Type
#####################################
day_type_cols = [
    "full_day_type",
]
day_type_title = [
    "Full Day Type",
]
segment_order_with_no = ["Upside", "Downside", "Inside", "Outside", "Undefined"]

day_type_row = st.columns(1)
for idx, col in enumerate(day_type_cols):
    if col in df_filtered:
        counts = (
            df_filtered[col]
            .value_counts(normalize=True)
            .reindex(segment_order_with_no, fill_value=0)
        )
        perc = counts * 100
        perc = perc[perc > 0]

        fig = px.bar(
            x=perc.index,
            y=perc.values,
            text=[f"{v:.1f}%" for v in perc.values],
            labels={"x": "", "y": ""},
            title=day_type_title[idx],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_tickangle=90,
            yaxis=dict(showticklabels=False),
            xaxis={"categoryorder": "array", "categoryarray": list(perc.index)},
            margin=dict(l=10, r=10, t=30, b=10),
        )

        day_type_row[idx].plotly_chart(fig, use_container_width=True)

#####################################
### Cycle Pair
#####################################
cycle_pair_col = [
    "cycle_pair",
]
cycle_pair_title = [
    "Cycle Pair",
]

cycle_pair_row = st.columns(1)
for idx, col in enumerate(cycle_pair_col):
    if col in df_filtered:
        counts = (
            df_filtered[col]
            .value_counts(normalize=True)
            #.reindex(segment_order_with_no, fill_value=0)
        )
        perc = counts * 100
        perc = perc[perc > 0]

        fig = px.bar(
            x=perc.index,
            y=perc.values,
            text=[f"{v:.1f}%" for v in perc.values],
            labels={"x": "", "y": ""},
            title=cycle_pair_title[idx],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_tickangle=90,
            yaxis=dict(showticklabels=False),
            xaxis={"categoryorder": "array", "categoryarray": list(perc.index)},
            margin=dict(l=10, r=10, t=30, b=10),
        )

        cycle_pair_row[idx].plotly_chart(fig, use_container_width=True)


st.caption(f"Sample size: {len(df_filtered):,} rows")
