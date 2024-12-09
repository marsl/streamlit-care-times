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

st.title("Einsätze Pflegedienst - Monatliche Übersicht")

@st.cache_data
def load_data():
    data = pd.read_csv("caregiver_times.csv")
    data['Date'] = pd.to_datetime(data['Date'], format='%d.%m.%Y')
    for col in ['Coming', 'Going']:
        data[col] = pd.to_datetime(data['Date'].astype(str) + ' ' + data[col])
    
    data['Duration'] = (data['Going'] - data['Coming']).dt.total_seconds() / 60
    data['Hour'] = data['Coming'].dt.hour + data['Coming'].dt.minute / 60
    data['Short_Visit'] = data['Duration'] < CONFIG['visit_thresholds']['short_visit']
    data['YearMonth'] = data['Date'].dt.to_period('M')
    return data

data = load_data()

# Month selector
months = sorted(data['YearMonth'].unique())
selected_month = st.selectbox('Monat', months, format_func=lambda x: x.strftime('%B %Y'))
month_data = data[data['YearMonth'] == selected_month]

# Monthly metrics
st.header(f"Monthly Analysis - {selected_month.strftime('%B %Y')}")
col1, col2, col3 = st.columns(3)

# Calculate metrics
monthly_minutes = month_data['Duration'].sum()
monthly_hours = monthly_minutes / 60
days_in_month = len(month_data['Date'].dt.date.unique())
total_days = calendar.monthrange(selected_month.year, selected_month.month)[1]

with col1:
    st.metric("Gesamt Stunden", 
              f"{monthly_hours:.1f}h",
              f"{monthly_minutes:.0f}min")

with col2:
    daily_hours = monthly_hours / days_in_month
    st.metric("Tagesdurchschnitt",
              f"{daily_hours:.1f}h/day",
              f"{(daily_hours * 60):.0f}min/day")

with col3:
    projected_hours = (monthly_hours / days_in_month) * total_days
    st.metric("Projektion Restmonat",
              f"{projected_hours:.1f}h",
              f"+{(projected_hours - monthly_hours):.1f}h remaining")

# Timeline visualization
st.header("Tägliche Besuche")
fig = go.Figure()

# Add period windows
for period, settings in CONFIG['periods'].items():
    fig.add_vrect(
        x0=settings['start'],
        x1=settings['end'],
        fillcolor="rgba(0,255,0,0.1)",
        layer="below",
        line_width=0,
        annotation_text=period,
        annotation_position="top left"
    )

# Plot visits for selected month
for date in sorted(month_data['Date'].dt.date.unique()):
    day_data = month_data[month_data['Date'].dt.date == date].sort_values('Coming')
    date_str = date.strftime('%d.%m')
    
    previous_going_hour = None
    
    for _, row in day_data.iterrows():
        coming_hour = row['Coming'].hour + row['Coming'].minute/60
        going_hour = row['Going'].hour + row['Going'].minute/60
        
        color = CONFIG['periods'][row['Time of day']]['color']
        if row['Short_Visit']:
            color = 'rgba(255,0,0,0.7)'
            
        fig.add_trace(go.Scatter(
            x=[coming_hour, going_hour],
            y=[date_str] * 2,
            mode='lines',
            line=dict(color=color, width=CONFIG['chart_settings']['bar_height']),
            showlegend=False,
            hovertemplate=(
                f"Date: {date_str}<br>" +
                f"Time: {row['Coming'].strftime('%H:%M')}-{row['Going'].strftime('%H:%M')}<br>" +
                f"Duration: {row['Duration']:.0f}min<br>" +
                f"Period: {row['Time of day']}"
            ),
            text=[f"{row['Duration']:.0f}min"],
            textposition="middle right"
        ))
        
        if previous_going_hour is not None:
            gap_duration = (coming_hour - previous_going_hour) * 60
            fig.add_trace(go.Scatter(
                x=[previous_going_hour, coming_hour],
                y=[date_str] * 2,
                mode='lines',
                line=dict(color=CONFIG['chart_settings']['gap_color'], width=CONFIG['chart_settings']['gap_line_width']),
                showlegend=False,
                hovertemplate=(
                    f"Date: {date_str}<br>" +
                    f"Gap: {gap_duration:.0f}min"
                )
            ))
        
        previous_going_hour = going_hour

fig.update_layout(
    title="Timeline Monat",
    xaxis_title="Uhrzeit",
    yaxis_title="Datum",
    height=800,
    xaxis=dict(
        tickmode='array',
        ticktext=[f'{i:02d}:00' for i in range(24)],
        tickvals=list(range(24))
    )
)

st.plotly_chart(fig, use_container_width=True)

# Monthly statistics
st.header("Monatsstatistik")
col1, col2, col3 = st.columns(3)

with col1:
    monthly_short_visits = month_data['Short_Visit'].sum()
    st.metric("Kurze Besuche",
              f"{monthly_short_visits}",
              f"{(monthly_short_visits/len(month_data)*100):.1f}%")

with col2:
    avg_duration = month_data.groupby('Time of day')['Duration'].mean()
    st.metric("Druchschnittsdauer",
              f"{avg_duration.mean():.0f}min",
              f"Bereich: {month_data['Duration'].min():.0f}-{month_data['Duration'].max():.0f}min")

with col3:
    visits_per_day = len(month_data) / days_in_month
    st.metric("Besuche pro Tag",
              f"{visits_per_day:.1f}",
              f"Total: {len(month_data)} Besuche")

# Distribution plots
col1, col2 = st.columns(2)

with col1:
    fig_dist = px.box(month_data,
                     x='Time of day',
                     y='Hour',
                     title="Besuchsverteilung",)
    st.plotly_chart(fig_dist)

with col2:
    hours_by_period = month_data.groupby('Time of day')['Duration'].sum() / 60
    fig_hours = px.bar(
        x=hours_by_period.index,
        y=hours_by_period.values,
        title="Stunden nach Tageszeit",
        labels={'x': 'Tageszeit', 'y': 'Stunden'},
        color=hours_by_period.index,
        color_discrete_map={
            'Morning': CONFIG['periods']['Morning']['color'],
            'Noon': CONFIG['periods']['Noon']['color'],
            'Evening': CONFIG['periods']['Evening']['color']
        }
    )
    st.plotly_chart(fig_hours)