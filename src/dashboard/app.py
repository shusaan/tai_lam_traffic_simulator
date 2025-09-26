"""Web dashboard for Tai Lam Traffic Simulator"""

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import threading
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulator.traffic_simulator import TrafficSimulator
from simulator.simple_pricing_model import SimplePricingModel as HybridPricingModel
from simple_data_processor import TrafficDataProcessor
from config import SCENARIOS, ROADS

# Initialize components
simulator = TrafficSimulator()
pricing_model = HybridPricingModel()
data_processor = TrafficDataProcessor()

# Initialize Dash app
app = dash.Dash(__name__)
app.title = "Tai Lam Traffic Simulator"

# Global variables for simulation state
simulation_running = False
simulation_thread = None
simulation_data = []

# AWS-themed dashboard layout
app.layout = html.Div([
    # Header with AWS branding
    html.Div([
        html.H1("🚇 Tai Lam AI Traffic Optimizer", className="header-title"),
        html.P("🤖 AWS-Powered Dynamic Toll Pricing & Smart Traffic Management", className="header-subtitle"),
        html.Div([
            html.Span("🏆 AWS Hackathon 2024", className="hackathon-badge"),
            html.Span("⚡ Real-time AI", className="ai-badge"),
            html.Span("🌏 Hong Kong", className="location-badge")
        ], className="badges")
    ], className="header"),
    
    # KPI Cards
    html.Div([
        html.Div([
            html.H3("💰 Revenue", className="kpi-title"),
            html.H2(id="revenue-kpi", className="kpi-value"),
            html.P("Target: HK$50K/hr", className="kpi-target")
        ], className="kpi-card revenue-card"),
        
        html.Div([
            html.H3("🚗 Traffic Flow", className="kpi-title"),
            html.H2(id="traffic-kpi", className="kpi-value"),
            html.P("Vehicles/hour", className="kpi-target")
        ], className="kpi-card traffic-card"),
        
        html.Div([
            html.H3("⚡ AI Toll Price", className="kpi-title"),
            html.H2(id="toll-kpi", className="kpi-value"),
            html.P("Dynamic pricing", className="kpi-target")
        ], className="kpi-card toll-card"),
        
        html.Div([
            html.H3("🎯 Efficiency", className="kpi-title"),
            html.H2(id="efficiency-kpi", className="kpi-value"),
            html.P("Traffic balance", className="kpi-target")
        ], className="kpi-card efficiency-card")
    ], className="kpi-row"),
    
    # Control Panel
    html.Div([
        html.Div([
            html.H3("🎮 Simulation Controls", className="panel-title"),
            html.Label("Traffic Scenario:", className="control-label"),
            dcc.Dropdown(
                id='scenario-dropdown',
                options=[
                    {'label': '🌅 Normal Traffic', 'value': 'normal'},
                    {'label': '🚗 Rush Hour Chaos', 'value': 'rush_hour'},
                    {'label': '🌧️ Rainstorm Impact', 'value': 'rainstorm'},
                    {'label': '🎵 Concert Night Surge', 'value': 'concert_night'}
                ],
                value='normal',
                className="scenario-dropdown"
            ),
            html.Div([
                html.Button('▶️ Start AI Simulation', id='start-btn', n_clicks=0, className="btn-start"),
                html.Button('⏹️ Stop', id='stop-btn', n_clicks=0, className="btn-stop"),
                html.Button('🔄 Reset', id='reset-btn', n_clicks=0, className="btn-reset"),
            ], className="button-group")
        ], className="control-panel"),
        
        html.Div([
            html.H3("📊 Live Status", className="panel-title"),
            html.Div(id="status-display", className="status-content"),
        ], className="status-panel")
    ], className="controls-row"),
    
    # Main Charts
    html.Div([
        html.Div([
            dcc.Graph(id='traffic-flow-chart', className="chart")
        ], className="chart-container"),
        
        html.Div([
            dcc.Graph(id='toll-price-chart', className="chart")
        ], className="chart-container"),
    ], className="charts-row"),
    
    html.Div([
        html.Div([
            dcc.Graph(id='congestion-heatmap', className="chart")
        ], className="chart-container"),
        
        html.Div([
            dcc.Graph(id='revenue-chart', className="chart")
        ], className="chart-container"),
    ], className="charts-row"),
    
    # Interactive Map
    html.Div([
        html.H3("🗺️ Real-time Hong Kong Traffic Map", className="map-title"),
        dcc.Graph(id='traffic-map', className="traffic-map")
    ], className="map-container"),
    
    # Footer
    html.Div([
        html.P("🚀 Built with AWS Lambda, DynamoDB, Kinesis & AI/ML | 🏆 AWS Hackathon 2024", className="footer-text")
    ], className="footer"),
    
    # Auto-refresh
    dcc.Interval(id='interval-component', interval=3000, n_intervals=0),
    dcc.Store(id='simulation-store', data=[])
])

# Callbacks
@app.callback(
    [Output('simulation-store', 'data'),
     Output('status-display', 'children')],
    [Input('interval-component', 'n_intervals'),
     Input('start-btn', 'n_clicks'),
     Input('stop-btn', 'n_clicks'),
     Input('reset-btn', 'n_clicks')],
    [State('scenario-dropdown', 'value'),
     State('simulation-store', 'data')]
)
def update_simulation(n_intervals, start_clicks, stop_clicks, reset_clicks, 
                     scenario, stored_data):
    global simulation_running, simulation_thread
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return stored_data, get_status_display()
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == 'start-btn' and not simulation_running:
        simulation_running = True
        simulation_thread = threading.Thread(
            target=run_simulation_background, 
            args=(scenario,)
        )
        simulation_thread.start()
        
    elif trigger_id == 'stop-btn':
        simulation_running = False
        
    elif trigger_id == 'reset-btn':
        simulation_running = False
        simulator.reset_simulation()
        stored_data = []
    
    # Update data if simulation is running
    if simulation_running and len(simulation_data) > len(stored_data):
        stored_data = simulation_data.copy()
    
    return stored_data, get_status_display()

@app.callback(
    Output('traffic-flow-chart', 'figure'),
    [Input('simulation-store', 'data')]
)
def update_traffic_flow_chart(data):
    if not data:
        return create_empty_chart("🚗 Traffic Flow")
    
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    fig = go.Figure()
    colors = ['#ef4444', '#3b82f6', '#10b981']
    
    for i, road_name in enumerate(['tai_lam_tunnel', 'tuen_mun_road', 'nt_circular_road']):
        if f'roads' in df.columns:
            vehicles = [row['roads'][road_name]['vehicles'] for row in data]
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=vehicles,
                mode='lines+markers',
                name=ROADS[road_name].name,
                line=dict(width=3, color=colors[i]),
                marker=dict(size=6)
            ))
    
    fig.update_layout(
        title="🚗 Real-time Traffic Flow",
        xaxis_title="Time",
        yaxis_title="Vehicles",
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter'),
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig

@app.callback(
    Output('toll-price-chart', 'figure'),
    [Input('simulation-store', 'data')]
)
def update_toll_price_chart(data):
    if not data:
        return create_empty_chart("💰 AI Toll Pricing")
    
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['toll_price'],
        mode='lines+markers',
        name='AI Toll Price',
        line=dict(color='#ef4444', width=4),
        marker=dict(size=8, color='#ef4444'),
        fill='tonexty',
        fillcolor='rgba(239, 68, 68, 0.1)'
    ))
    
    fig.update_layout(
        title="💰 AI-Powered Dynamic Toll Pricing",
        xaxis_title="Time",
        yaxis_title="Price (HKD)",
        yaxis=dict(range=[5, 25]),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter'),
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig

@app.callback(
    Output('congestion-heatmap', 'figure'),
    [Input('simulation-store', 'data')]
)
def update_congestion_heatmap(data):
    if not data:
        return create_empty_chart("Congestion Levels")
    
    # Get latest data point
    latest_data = data[-1] if data else {}
    roads_data = latest_data.get('roads', {})
    
    road_names = list(ROADS.keys())
    congestion_levels = [roads_data.get(road, {}).get('congestion', 0) for road in road_names]
    
    fig = go.Figure(data=go.Bar(
        x=[ROADS[road].name for road in road_names],
        y=congestion_levels,
        marker_color=['red' if c > 0.8 else 'orange' if c > 0.5 else 'green' 
                     for c in congestion_levels]
    ))
    
    fig.update_layout(
        title="Current Congestion Levels",
        xaxis_title="Road",
        yaxis_title="Congestion Level",
        yaxis=dict(range=[0, 1])
    )
    
    return fig

@app.callback(
    Output('revenue-chart', 'figure'),
    [Input('simulation-store', 'data')]
)
def update_revenue_chart(data):
    if not data:
        return create_empty_chart("Revenue")
    
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['revenue'],
        mode='lines+markers',
        name='Cumulative Revenue',
        line=dict(color='green', width=3),
        fill='tonexty'
    ))
    
    fig.update_layout(
        title="Tunnel Revenue",
        xaxis_title="Time",
        yaxis_title="Revenue (HKD)"
    )
    
    return fig

@app.callback(
    Output('traffic-map', 'figure'),
    [Input('simulation-store', 'data')]
)
def update_traffic_map(data):
    if not data:
        return create_empty_map()
    
    latest_data = data[-1] if data else {}
    roads_data = latest_data.get('roads', {})
    
    fig = go.Figure()
    
    # Add road segments
    for road_name, road_config in ROADS.items():
        congestion = roads_data.get(road_name, {}).get('congestion', 0)
        
        # Color based on congestion
        color = 'red' if congestion > 0.8 else 'orange' if congestion > 0.5 else 'green'
        width = max(2, congestion * 10)
        
        lats = [coord[0] for coord in road_config.coordinates]
        lons = [coord[1] for coord in road_config.coordinates]
        
        fig.add_trace(go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode='lines',
            line=dict(width=width, color=color),
            name=road_config.name,
            hovertemplate=f"<b>{road_config.name}</b><br>" +
                         f"Congestion: {congestion:.1%}<br>" +
                         f"Vehicles: {roads_data.get(road_name, {}).get('vehicles', 0)}<extra></extra>"
        ))
    
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=22.4, lon=114.05),
            zoom=10
        ),
        title="Real-time Traffic Map",
        height=500
    )
    
    return fig

def create_empty_chart(title):
    """Create empty chart placeholder"""
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        annotations=[dict(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16)
        )]
    )
    return fig

def create_empty_map():
    """Create empty map placeholder"""
    fig = go.Figure()
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=22.4, lon=114.05),
            zoom=10
        ),
        title="Traffic Map",
        height=500
    )
    return fig

def get_status_display():
    """Get current simulation status"""
    status = "🟢 Running" if simulation_running else "🔴 Stopped"
    current_time = simulator.current_time.strftime("%H:%M:%S")
    current_toll = f"HK${simulator.toll_price:.2f}"
    total_revenue = f"HK${simulator.revenue:.2f}"
    
    return html.Div([
        html.P([html.Strong("Status: "), status]),
        html.P([html.Strong("Time: "), f"⏰ {current_time}"]),
        html.P([html.Strong("Current Toll: "), f"💰 {current_toll}"]),
        html.P([html.Strong("Revenue: "), f"📈 {total_revenue}"])
    ])

def run_simulation_background(scenario):
    """Run simulation in background thread"""
    global simulation_data
    
    prev_state = None
    
    while simulation_running:
        # Run simulation step
        traffic_snapshot = simulator.simulate_step(scenario)
        simulation_data.append(traffic_snapshot)
        
        # Update toll price every 15 minutes
        if len(simulation_data) % 15 == 0:
            current_state = simulator.get_current_state()
            new_toll = pricing_model.get_price_recommendation(current_state)
            simulator.update_toll_price(new_toll)
            
            # Train ML model
            if prev_state:
                pricing_model.train_step(prev_state, simulator.toll_price, current_state)
            
            prev_state = current_state
        
        # Stream to AWS (optional)
        try:
            data_processor.simulate_traffic_stream(traffic_snapshot)
        except Exception as e:
            print(f"AWS streaming error: {e}")
        
        # Keep only last 1000 data points
        if len(simulation_data) > 1000:
            simulation_data = simulation_data[-1000:]
        
        time.sleep(1)  # 1 second per simulation minute

# Add KPI callbacks
@app.callback(
    [Output('revenue-kpi', 'children'),
     Output('traffic-kpi', 'children'),
     Output('toll-kpi', 'children'),
     Output('efficiency-kpi', 'children')],
    [Input('simulation-store', 'data')]
)
def update_kpis(data):
    if not data:
        return "HK$0", "0", "HK$8.00", "0%"
    
    latest = data[-1]
    revenue = f"HK${latest['revenue']:.0f}"
    
    total_vehicles = sum(latest['roads'][road]['vehicles'] for road in latest['roads'])
    traffic = f"{total_vehicles * 60:,}"
    
    toll = f"HK${latest['toll_price']:.2f}"
    
    # Calculate efficiency as traffic balance
    congestions = [latest['roads'][road]['congestion'] for road in latest['roads']]
    efficiency = f"{(1 - (max(congestions) - min(congestions))) * 100:.0f}%"
    
    return revenue, traffic, toll, efficiency

# Enhanced chart styling
def update_chart_style(fig, title, color_scheme='aws'):
    colors = {
        'aws': ['#FF9900', '#232F3E', '#146EB4'],
        'traffic': ['#27ae60', '#e74c3c', '#f39c12']
    }
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color='#2c3e50')),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, sans-serif'),
        margin=dict(l=20, r=20, t=60, b=20)
    )
    return fig

if __name__ == '__main__':
    # Add custom CSS
    app.index_string = '''
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: 'Inter', sans-serif; background: #f8fafc; }
                
                /* Header */
                .header { background: linear-gradient(135deg, #FF9900 0%, #232F3E 100%); color: white; padding: 40px 20px; text-align: center; position: relative; overflow: hidden; }
                .header::before { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 20"><defs><radialGradient id="a" cx="50%" cy="0%" r="100%"><stop offset="0%" stop-color="%23fff" stop-opacity=".1"/><stop offset="100%" stop-color="%23fff" stop-opacity="0"/></radialGradient></defs><rect width="100" height="20" fill="url(%23a)"/></svg>'); }
                .header-title { font-size: 2.8rem; font-weight: 800; margin-bottom: 8px; position: relative; z-index: 1; }
                .header-subtitle { font-size: 1.1rem; opacity: 0.95; margin-bottom: 25px; position: relative; z-index: 1; }
                .badges { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; position: relative; z-index: 1; }
                .hackathon-badge, .ai-badge, .location-badge { background: rgba(255,255,255,0.15); padding: 6px 14px; border-radius: 20px; font-weight: 600; font-size: 0.85rem; border: 1px solid rgba(255,255,255,0.2); }
                
                /* KPI Cards */
                .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; padding: 30px; max-width: 1200px; margin: 0 auto; }
                .kpi-card { background: white; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.08); transition: all 0.3s ease; border-top: 4px solid; }
                .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(0,0,0,0.15); }
                .revenue-card { border-top-color: #10b981; }
                .traffic-card { border-top-color: #3b82f6; }
                .toll-card { border-top-color: #ef4444; }
                .efficiency-card { border-top-color: #f59e0b; }
                .kpi-title { font-size: 0.9rem; color: #6b7280; margin-bottom: 8px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
                .kpi-value { font-size: 2.2rem; font-weight: 700; margin-bottom: 4px; }
                .revenue-card .kpi-value { color: #10b981; }
                .traffic-card .kpi-value { color: #3b82f6; }
                .toll-card .kpi-value { color: #ef4444; }
                .efficiency-card .kpi-value { color: #f59e0b; }
                .kpi-target { color: #9ca3af; font-size: 0.8rem; }
                
                /* Controls */
                .controls-row { display: grid; grid-template-columns: 2fr 1fr; gap: 25px; padding: 0 30px; margin-bottom: 30px; max-width: 1200px; margin-left: auto; margin-right: auto; }
                .control-panel, .status-panel { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
                .panel-title { color: #1f2937; font-size: 1.2rem; font-weight: 700; margin-bottom: 20px; display: flex; align-items: center; gap: 8px; }
                .control-label { color: #4b5563; font-weight: 600; margin-bottom: 8px; display: block; font-size: 0.9rem; }
                .scenario-dropdown { margin-bottom: 20px; }
                .Select-control { border: 2px solid #e5e7eb !important; border-radius: 8px !important; }
                .button-group { display: flex; gap: 12px; flex-wrap: wrap; }
                .btn-start, .btn-stop, .btn-reset { border: none; padding: 12px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; font-size: 0.9rem; display: flex; align-items: center; gap: 6px; }
                .btn-start { background: #10b981; color: white; }
                .btn-stop { background: #ef4444; color: white; }
                .btn-reset { background: #6b7280; color: white; }
                .btn-start:hover { background: #059669; }
                .btn-stop:hover { background: #dc2626; }
                .btn-reset:hover { background: #4b5563; }
                
                /* Status Panel */
                .status-content { background: #f9fafb; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6; }
                .status-content p { margin: 4px 0; font-size: 0.9rem; color: #374151; }
                
                /* Charts */
                .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; padding: 0 30px; margin-bottom: 30px; max-width: 1200px; margin-left: auto; margin-right: auto; }
                .chart-container { background: white; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); overflow: hidden; }
                
                /* Map */
                .map-container { background: white; margin: 0 30px 30px; border-radius: 12px; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); max-width: 1200px; margin-left: auto; margin-right: auto; }
                .map-title { color: #1f2937; font-size: 1.3rem; font-weight: 700; margin-bottom: 20px; text-align: center; display: flex; align-items: center; justify-content: center; gap: 8px; }
                
                /* Footer */
                .footer { background: #1f2937; color: #d1d5db; text-align: center; padding: 20px; }
                .footer-text { font-size: 0.9rem; }
                
                /* Responsive */
                @media (max-width: 1024px) {
                    .kpi-row { grid-template-columns: repeat(2, 1fr); }
                    .controls-row { grid-template-columns: 1fr; }
                }
                @media (max-width: 768px) {
                    .header-title { font-size: 2rem; }
                    .kpi-row, .charts-row { grid-template-columns: 1fr; }
                    .badges { justify-content: center; }
                    .button-group { justify-content: center; }
                }
                @media (max-width: 480px) {
                    .header { padding: 30px 15px; }
                    .kpi-row, .controls-row, .charts-row { padding: 0 15px; }
                    .map-container { margin: 0 15px 30px; }
                }
            </style>
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    '''
    app.run(debug=True, host='0.0.0.0', port=8050)