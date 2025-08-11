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
st.title("Trompete Kostet Knete")

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

st.write(len(df))
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

st.markdown("### Dropdown Filters")



#########################################
### Model Filters
#########################################
with st.expander("Models", expanded=False):
    row1_cols = st.columns([1, 1, 1, 1])
    with row1_cols[0]:
        prev_rdr_to_adr_model_filter = st.multiselect(
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

    "odr_to_rdr_model" : "odr_to_rdr_model_filter",
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

#for col, state_key in exclusion_map.items():
    #excludes = st.session_state[state_key]
    #if excludes:
        #df_filtered = df_filtered[~df_filtered[col].isin(excludes)]

for col, state_key in exclusion_map.items():
    sel = st.session_state[state_key]   # now either "None" or a segment string
    if sel != "None":
        # build the full cascade from start up through 'sel'
        idx = segment_order.index(sel)
        to_exclude = set(segment_order[: idx+1])
        df_filtered = df_filtered[~df_filtered[col].isin(to_exclude)]
  

#########################################################
### Models Graphs
#########################################################
model_cols = [
    "prev_rdr_to_adr_model",
    "adr_to_odr_model",
    "prev_rdr_to_odr_model",
    "odr_to_rdr_model"]

model_titles = [
    "PRDR-ADR Model",
    "ADR-ODR Model",
    "PRDR-ODR Model",
    "ODR-RDR Model"]

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

    row1[idx].plotly_chart(fig, use_container_width=True)


#########################################################
### HoD / LoD Session Buckets
#########################################################
hod_lod_cols = [
    "hod",
    "lod",
]
hod_lod_titles = [
    "High of Day",
    "Low of Day"
]

hod_lod_row = st.columns(2)
for idx, col in enumerate(hod_lod_cols):
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
            title=hod_lod_titles[idx],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_tickangle=90,
            yaxis=dict(showticklabels=False),
            xaxis={"categoryorder": "array", "categoryarray": list(perc.index)},
            margin=dict(l=10, r=10, t=30, b=10),
        )

        hod_lod_row[idx].plotly_chart(fig, use_container_width=True)

#########################################################
### HoD / LoD 5m Buckets
#########################################################
times = [f"{h:02d}:{m:02d}" 
         for h in range(24) 
         for m in range(0, 60, 5)]

first_half  = [t for t in times if "18:00" <= t <= "23:55"]
second_half = [t for t in times if "00:00" <= t <= "15:55"]
rotated = first_half + second_half

hod_hm_cols = [
    "hod_hm",
]
hod_hm_titles = [
    "High of Day (5m)",
]

hod_row_hm = st.columns(len(hod_hm_cols))
for idx, col in enumerate(hod_hm_cols):
    if col in df_filtered:
        counts = (
            df_filtered[col]
            .value_counts(normalize=True)
        )
        perc = counts * 100
        perc = perc[perc > 0]

        y_vals = [perc.get(t, 0) for t in rotated]
        txt    = [f"{v:.1f}%"    for v in y_vals]

        fig = px.bar(
            x=rotated,
            y=y_vals,
            text=txt,
            labels={"x": "", "y": ""},
            title=hod_hm_titles[idx],
        )
        fig.update_traces(textposition="outside")
        fig.update_xaxes(categoryorder="array",
                        categoryarray=rotated,
                        tickangle=90)
        fig.update_layout(
            yaxis=dict(showticklabels=False),
            margin=dict(l=10, r=10, t=30, b=10),
        )

        hod_row_hm[idx].plotly_chart(fig, use_container_width=True)

lod_hm_cols = [
    "lod_hm",
]
lod_hm_titles = [
    "Low of Day (5m)",
]

lod_row_hm = st.columns(len(lod_hm_cols))
for idx, col in enumerate(lod_hm_cols):
    if col in df_filtered:
        counts = (
            df_filtered[col]
            .value_counts(normalize=True)
        )
        perc = counts * 100
        perc = perc[perc > 0]

        y_vals = [perc.get(t, 0) for t in rotated]
        txt    = [f"{v:.1f}%"    for v in y_vals]

        fig = px.bar(
            x=rotated,
            y=y_vals,
            text=txt,
            labels={"x": "", "y": ""},
            title=lod_hm_titles[idx],
        )
        fig.update_traces(textposition="outside")
        fig.update_xaxes(categoryorder="array",
                        categoryarray=rotated,
                        tickangle=90)
        fig.update_layout(
            yaxis=dict(showticklabels=False),
            margin=dict(l=10, r=10, t=30, b=10),
        )

        lod_row_hm[idx].plotly_chart(fig, use_container_width=True)

#########################################################
### Partial Day Highs/Lows 5m Buckets
#########################################################


        
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
    "day_type",
]
day_type_title = [
    "Day Type",
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


st.caption(f"Sample size: {len(df_filtered):,} rows")
