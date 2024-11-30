import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import calendar

# Configuration variables
CONFIG = {
    'periods': {
        'Morning': {'start': 6, 'end': 10, 'color': 'rgba(255,165,0,0.7)'},  # Orange
        'Noon': {'start': 11.5, 'end': 14, 'color': 'rgba(30,144,255,0.7)'},  # DodgerBlue
        'Evening': {'start': 17, 'end': 20, 'color': 'rgba(148,0,211,0.7)'}  # DarkViolet
    },
    'visit_thresholds': {
        'short_visit': 10,  # minutes
        'short_gap': 150,    # minutes
    },
    'chart_settings': {
        'bar_height': 20,
        'gap_color': 'rgba(255,0,0,0.3)',
        'gap_line_width': 2
    }
}

st.title("Caregiver Time Analysis - Quality of Care")

# Load and prepare data
@st.cache_data
def load_data():
    data = pd.read_csv("caregiver_times.csv")
    
    # Convert times to datetime
    data['Date'] = pd.to_datetime(data['Date'], format='%d.%m.%Y')
    for col in ['Coming', 'Going']:
        data[col] = pd.to_datetime(data['Date'].astype(str) + ' ' + data[col])
    
    # Calculate metrics
    data['Duration'] = (data['Going'] - data['Coming']).dt.total_seconds() / 60
    data['Hour'] = data['Coming'].dt.hour + data['Coming'].dt.minute / 60
    
    # Flag problematic visits
    data['Short_Visit'] = data['Duration'] < CONFIG['visit_thresholds']['short_visit']
    
    return data

data = load_data()

# Hours Analysis
st.header("Hours Analysis")
col1, col2, col3 = st.columns(3)

# Calculate total hours
total_minutes = data['Duration'].sum()
total_hours = total_minutes / 60

# Get month info
current_month = data['Date'].dt.month.iloc[0]
current_year = data['Date'].dt.year.iloc[0]
days_in_month = calendar.monthrange(current_year, current_month)[1]
current_day = data['Date'].dt.day.max()

with col1:
    st.metric("Total Hours Used", 
              f"{total_hours:.1f} hours",
              f"{total_minutes:.0f} minutes")

with col2:
    daily_hours = total_hours / len(data['Date'].dt.date.unique())
    st.metric("Average Daily Hours",
              f"{daily_hours:.1f} hours/day",
              f"{(daily_hours * 60):.0f} minutes/day")

with col3:
    # Get the first and last day we have data for
    first_day = data['Date'].dt.day.min()
    last_day = data['Date'].dt.day.max()
    total_days_covered = last_day - first_day + 1
    
    # Calculate daily average based on days we have data for
    daily_average = total_hours / total_days_covered
    
    # Calculate forecast for full month
    forecasted_total = daily_average * days_in_month
    
    st.metric("Forecasted Month Total",
             f"{forecasted_total:.1f} hours",
             f"+{(forecasted_total - total_hours):.1f} hours remaining")

# Daily Timeline View
st.header("Daily Care Visit Patterns")

# Create figure
fig = go.Figure()

# Add period windows
for period, settings in CONFIG['periods'].items():
    fig.add_vrect(
        x0=settings['start'], 
        x1=settings['end'],
        fillcolor="rgba(0,255,0,0.1)", 
        layer="below", 
        line_width=0,
        annotation_text=f"{period} ({settings['start']:02.1f}-{settings['end']:02.1f})",
        annotation_position="top left"
    )

# Process visits day by day
for date in sorted(data['Date'].dt.date.unique()):
    day_data = data[data['Date'].dt.date == date].sort_values('Coming')
    date_str = day_data.iloc[0]['Date'].strftime('%d.%m')
    
    # Add visits as bars
    for _, row in day_data.iterrows():
        coming_hour = row['Coming'].hour + row['Coming'].minute/60
        going_hour = row['Going'].hour + row['Going'].minute/60
        
        color = CONFIG['periods'][row['Time of day']]['color']
        if row['Duration'] < CONFIG['visit_thresholds']['short_visit']:
            color = 'rgba(255,0,0,0.7)'  # Red for short visits
            
        fig.add_trace(go.Scatter(
            x=[coming_hour, going_hour],
            y=[date_str] * 2,
            mode='lines',
            line=dict(color=color, width=CONFIG['chart_settings']['bar_height']),
            name=row['Time of day'],
            showlegend=False,
            hovertemplate=(
                f"Date: {date_str}<br>" +
                f"Time: {row['Coming'].strftime('%H:%M')}-{row['Going'].strftime('%H:%M')}<br>" +
                f"Duration: {row['Duration']:.0f} min<br>" +
                f"Period: {row['Time of day']}"
            )
        ))
        
        # Add gaps between visits if they're too short
        if _ < len(day_data) - 1:
            next_row = day_data.iloc[_ + 1]
            gap_duration = (next_row['Coming'] - row['Going']).total_seconds() / 60
            
            if gap_duration < CONFIG['visit_thresholds']['short_gap']:
                fig.add_trace(go.Scatter(
                    x=[going_hour, next_row['Coming'].hour + next_row['Coming'].minute/60],
                    y=[date_str] * 2,
                    mode='lines',
                    line=dict(
                        color=CONFIG['chart_settings']['gap_color'],
                        width=CONFIG['chart_settings']['gap_line_width'],
                        dash='dot'
                    ),
                    showlegend=False,
                    hovertemplate=f"Gap duration: {gap_duration:.0f} min"
                ))

fig.update_layout(
    title=f"Care Visit Timeline (Red = visits shorter than {CONFIG['visit_thresholds']['short_visit']} minutes)",
    xaxis_title="Hour of Day",
    yaxis_title="Date",
    height=800,
    xaxis=dict(
        tickmode='array',
        ticktext=[f'{i:02d}:00' for i in range(24)],
        tickvals=list(range(24))
    )
)

st.plotly_chart(fig, use_container_width=True)

# Statistics
st.header("Care Quality Metrics")
col1, col2, col3 = st.columns(3)

# Calculate short visits
with col1:
    st.metric(f"Short Visits (<{CONFIG['visit_thresholds']['short_visit']} min)", 
              f"{data['Short_Visit'].sum()} visits",
              f"{(data['Short_Visit'].sum()/len(data)*100):.1f}% of all visits")

# Calculate gaps
all_gaps = []
for date in data['Date'].dt.date.unique():
    day_data = data[data['Date'].dt.date == date].sort_values('Coming')
    for i in range(len(day_data) - 1):
        gap = (day_data.iloc[i + 1]['Coming'] - day_data.iloc[i]['Going']).total_seconds() / 60
        all_gaps.append(gap)

with col2:
    short_gaps = sum(gap < CONFIG['visit_thresholds']['short_gap'] for gap in all_gaps)
    st.metric(f"Short Gaps (<{CONFIG['visit_thresholds']['short_gap']/60}h)", 
              f"{short_gaps} gaps",
              f"{(short_gaps/len(all_gaps)*100):.1f}% of all gaps")

with col3:
    avg_duration = data.groupby('Time of day')['Duration'].mean()
    st.metric("Overall Average Duration", 
              f"{avg_duration.mean():.0f} min",
              f"Range: {data['Duration'].min():.0f}-{data['Duration'].max():.0f} min")
    
# Time distribution analysis
st.header("Visit Time Distribution")
fig_dist = px.box(data, 
                  x='Time of day', 
                  y='Hour',
                  title="Distribution of Visit Times by Period",
                  labels={'Hour': 'Hour of Day'})

# Add period ranges
for period, settings in CONFIG['periods'].items():
    fig_dist.add_hline(
        y=settings['start'], 
        line_dash="dash", 
        line_color="green", 
        annotation_text=f"{period} Start"
    )
    fig_dist.add_hline(
        y=settings['end'], 
        line_dash="dash", 
        line_color="red", 
        annotation_text=f"{period} End"
    )

st.plotly_chart(fig_dist)

# Hours by period
hours_by_period = data.groupby('Time of day', sort=False)['Duration'].sum() / 60

fig_hours = px.bar(
    x=hours_by_period.index,
    y=hours_by_period.values,
    title="Hours by Period",
    labels={'x': 'Period', 'y': 'Hours'},
    color=hours_by_period.index,
    color_discrete_map={
        'Morning': CONFIG['periods']['Morning']['color'],
        'Noon': CONFIG['periods']['Noon']['color'],
        'Evening': CONFIG['periods']['Evening']['color']
    }
)
st.plotly_chart(fig_hours)