"""Fixed modern dashboard for Tai Lam Traffic Simulator"""

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime
import threading
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulator.traffic_simulator import TrafficSimulator
from simulator.trained_pricing_model import TrainedPricingModel as HybridPricingModel
from simple_data_processor import TrafficDataProcessor
from config import SCENARIOS, ROADS

# Initialize components
simulator = TrafficSimulator()
pricing_model = HybridPricingModel()
data_processor = TrafficDataProcessor()

# Initialize Dash app
app = dash.Dash(__name__)
app.title = "Tai Lam AI Traffic Optimizer"

# Global variables
simulation_running = False
simulation_thread = None
simulation_data = []

# Fixed dashboard layout
app.layout = html.Div([
    # Sidebar
    html.Div([
        html.Div([
            html.Div("🚗", className="logo-icon"),
            html.H2("Tai Lam AI", className="sidebar-title"),
            html.P("Traffic Optimizer", className="sidebar-subtitle")
        ], className="sidebar-header"),
        
        html.Div([
            html.H4("🎮 Controls", className="section-title"),
            html.Label("Scenario", className="input-label"),
            dcc.Dropdown(
                id='scenario-dropdown',
                options=[
                    {'label': '🌅 Normal', 'value': 'normal'},
                    {'label': '🚗 Rush Hour', 'value': 'rush_hour'},
                    {'label': '🌧️ Rainstorm', 'value': 'rainstorm'},
                    {'label': '🎵 Concert Night', 'value': 'concert_night'}
                ],
                value='normal',
                className="modern-dropdown",
                style={'color': '#000000', 'backgroundColor': '#ffffff'}
            ),
            html.Div([
                html.Button('▶️ Start', id='start-btn', n_clicks=0, className="btn-primary"),
                html.Button('⏹️ Stop', id='stop-btn', n_clicks=0, className="btn-secondary"),
                html.Button('🔄 Reset', id='reset-btn', n_clicks=0, className="btn-tertiary"),
            ], className="button-grid"),
            
            html.Div([
                html.H4("📊 Status", className="section-title"),
                html.Div(id="status-display", className="status-box")
            ], className="status-section")
        ], className="sidebar-content")
    ], className="sidebar"),
    
    # Main content
    html.Div([
        # Header
        html.Div([
            html.H1("🚗 Tai Lam AI Traffic Optimizer", className="main-title"),
            html.P("AWS-Powered Dynamic Toll Pricing System", className="main-subtitle"),
            html.Div([
                html.Span("🏆 AWS Hackathon 2024", className="badge"),
                html.Span("⚡ Real-time AI", className="badge"),
                html.Span("🇭🇰 Hong Kong", className="badge")
            ], className="badge-container")
        ], className="main-header"),
        
        # KPI Grid
        html.Div([
            html.Div([
                html.Div("💰", className="kpi-icon"),
                html.Div([
                    html.H3(id="revenue-kpi", className="kpi-value"),
                    html.P("Revenue", className="kpi-label")
                ])
            ], className="kpi-card revenue"),
            
            html.Div([
                html.Div("🚗", className="kpi-icon"),
                html.Div([
                    html.H3(id="traffic-kpi", className="kpi-value"),
                    html.P("Traffic Flow", className="kpi-label")
                ])
            ], className="kpi-card traffic"),
            
            html.Div([
                html.Div("⚡", className="kpi-icon"),
                html.Div([
                    html.H3(id="toll-kpi", className="kpi-value"),
                    html.P("AI Toll Price", className="kpi-label")
                ])
            ], className="kpi-card toll"),
            
            html.Div([
                html.Div("🎯", className="kpi-icon"),
                html.Div([
                    html.H3(id="efficiency-kpi", className="kpi-value"),
                    html.P("Efficiency", className="kpi-label")
                ])
            ], className="kpi-card efficiency")
        ], className="kpi-grid"),
        
        # Charts Grid
        html.Div([
            html.Div([
                dcc.Graph(id='traffic-flow-chart', className="chart")
            ], className="chart-card"),
            
            html.Div([
                dcc.Graph(id='toll-price-chart', className="chart")
            ], className="chart-card"),
            
            html.Div([
                dcc.Graph(id='congestion-heatmap', className="chart")
            ], className="chart-card"),
            
            html.Div([
                dcc.Graph(id='revenue-chart', className="chart")
            ], className="chart-card")
        ], className="charts-grid"),
        
        # Map Section
        html.Div([
            html.H3("🗺️ Real-time Hong Kong Traffic Map", className="map-title"),
            dcc.Graph(id='traffic-map', className="map-chart")
        ], className="map-section")
    ], className="main-content"),
    
    # Auto-refresh
    dcc.Interval(id='interval-component', interval=2000, n_intervals=0),
    dcc.Store(id='simulation-store', data=[])
], className="app-container")

# Callbacks (same as before)
@app.callback(
    [Output('simulation-store', 'data'), Output('status-display', 'children')],
    [Input('interval-component', 'n_intervals'), Input('start-btn', 'n_clicks'),
     Input('stop-btn', 'n_clicks'), Input('reset-btn', 'n_clicks')],
    [State('scenario-dropdown', 'value'), State('simulation-store', 'data')]
)
def update_simulation(n_intervals, start_clicks, stop_clicks, reset_clicks, scenario, stored_data):
    global simulation_running, simulation_thread
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return stored_data, get_status_display()
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == 'start-btn' and not simulation_running:
        simulation_running = True
        simulation_thread = threading.Thread(target=run_simulation_background, args=(scenario,))
        simulation_thread.start()
    elif trigger_id == 'stop-btn':
        simulation_running = False
    elif trigger_id == 'reset-btn':
        simulation_running = False
        simulator.reset_simulation()
        stored_data = []
    
    if simulation_running and len(simulation_data) > len(stored_data):
        stored_data = simulation_data.copy()
    
    return stored_data, get_status_display()

@app.callback(
    [Output('revenue-kpi', 'children'), Output('traffic-kpi', 'children'),
     Output('toll-kpi', 'children'), Output('efficiency-kpi', 'children')],
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
    congestions = [latest['roads'][road]['congestion'] for road in latest['roads']]
    efficiency = f"{(1 - (max(congestions) - min(congestions))) * 100:.0f}%"
    
    return revenue, traffic, toll, efficiency

@app.callback(Output('traffic-flow-chart', 'figure'), [Input('simulation-store', 'data')])
def update_traffic_flow_chart(data):
    fig = go.Figure()
    if data:
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
        
        for i, road_name in enumerate(['tai_lam_tunnel', 'tuen_mun_road', 'nt_circular_road']):
            vehicles = [row['roads'][road_name]['vehicles'] for row in data]
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=vehicles,
                mode='lines+markers',
                name=ROADS[road_name].name,
                line=dict(width=3, color=colors[i]),
                marker=dict(size=6)
            ))
    
    fig.update_layout(
        title="🚗 Traffic Flow",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter', size=12),
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

@app.callback(Output('toll-price-chart', 'figure'), [Input('simulation-store', 'data')])
def update_toll_price_chart(data):
    fig = go.Figure()
    if data:
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['toll_price'],
            mode='lines+markers',
            name='AI Toll Price',
            line=dict(color='#FF6B6B', width=4),
            marker=dict(size=8),
            fill='tonexty',
            fillcolor='rgba(255, 107, 107, 0.1)'
        ))
    
    fig.update_layout(
        title="⚡ AI Toll Pricing",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter', size=12),
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis=dict(range=[5, 25])
    )
    return fig

@app.callback(Output('congestion-heatmap', 'figure'), [Input('simulation-store', 'data')])
def update_congestion_heatmap(data):
    fig = go.Figure()
    if data:
        latest_data = data[-1]
        roads_data = latest_data.get('roads', {})
        road_names = list(ROADS.keys())
        congestion_levels = [roads_data.get(road, {}).get('congestion', 0) for road in road_names]
        
        fig.add_trace(go.Bar(
            x=[ROADS[road].name for road in road_names],
            y=congestion_levels,
            marker_color=['#FF6B6B' if c > 0.8 else '#FFD93D' if c > 0.5 else '#6BCF7F' for c in congestion_levels],
            text=[f'{c:.1%}' for c in congestion_levels],
            textposition='auto'
        ))
    
    fig.update_layout(
        title="🚦 Congestion Levels",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter', size=12),
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis=dict(range=[0, 1], tickformat='.0%')
    )
    return fig

@app.callback(Output('revenue-chart', 'figure'), [Input('simulation-store', 'data')])
def update_revenue_chart(data):
    fig = go.Figure()
    if data:
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['revenue'],
            mode='lines+markers',
            name='Revenue',
            line=dict(color='#6BCF7F', width=3),
            fill='tonexty',
            fillcolor='rgba(107, 207, 127, 0.2)'
        ))
    
    fig.update_layout(
        title="💰 Revenue Growth",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter', size=12),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

@app.callback(Output('traffic-map', 'figure'), [Input('simulation-store', 'data')])
def update_traffic_map(data):
    fig = go.Figure()
    if data:
        latest_data = data[-1]
        roads_data = latest_data.get('roads', {})
        
        for road_name, road_config in ROADS.items():
            congestion = roads_data.get(road_name, {}).get('congestion', 0)
            color = '#FF6B6B' if congestion > 0.8 else '#FFD93D' if congestion > 0.5 else '#6BCF7F'
            width = max(3, congestion * 12)
            
            lats = [coord[0] for coord in road_config.coordinates]
            lons = [coord[1] for coord in road_config.coordinates]
            
            fig.add_trace(go.Scatter(
                x=lons, y=lats,
                mode='lines',
                line=dict(width=width, color=color),
                name=road_config.name,
                hovertemplate=f"<b>{road_config.name}</b><br>Congestion: {congestion:.1%}<extra></extra>"
            ))
    
    fig.update_layout(
        title="Hong Kong Traffic Map",
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def get_status_display():
    status = "🟢 Running" if simulation_running else "🔴 Stopped"
    time_str = simulator.current_time.strftime("%H:%M:%S")
    toll = f"HK${simulator.toll_price:.2f}"
    revenue = f"HK${simulator.revenue:.2f}"
    
    return html.Div([
        html.Div([html.Span("Status"), html.Span(status)], className="status-item"),
        html.Div([html.Span("Time"), html.Span(time_str)], className="status-item"),
        html.Div([html.Span("Toll"), html.Span(toll)], className="status-item"),
        html.Div([html.Span("Revenue"), html.Span(revenue)], className="status-item")
    ])

def run_simulation_background(scenario):
    global simulation_data
    prev_state = None
    
    while simulation_running:
        traffic_snapshot = simulator.simulate_step(scenario)
        simulation_data.append(traffic_snapshot)
        
        if len(simulation_data) % 15 == 0:
            current_state = simulator.get_current_state()
            new_toll = pricing_model.get_price_recommendation(current_state)
            simulator.update_toll_price(new_toll)
            
            if prev_state:
                pricing_model.train_step(prev_state, simulator.toll_price, current_state)
            prev_state = current_state
        
        if len(simulation_data) > 1000:
            simulation_data = simulation_data[-1000:]
        
        time.sleep(1)

if __name__ == '__main__':
    # Fixed CSS with proper dropdown styling
    app.index_string = '''
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: 'Inter', sans-serif; background: #f8fafc; }
                
                .app-container { display: flex; min-height: 100vh; }
                
                /* Sidebar */
                .sidebar { width: 280px; background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); color: white; padding: 0; box-shadow: 4px 0 20px rgba(0,0,0,0.1); }
                .sidebar-header { padding: 30px 25px; border-bottom: 1px solid rgba(255,255,255,0.1); }
                .logo-icon { font-size: 2.5rem; margin-bottom: 15px; }
                .sidebar-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 5px; }
                .sidebar-subtitle { font-size: 0.9rem; opacity: 0.7; }
                .sidebar-content { padding: 25px; }
                .section-title { font-size: 1rem; font-weight: 600; margin-bottom: 15px; color: #e2e8f0; }
                .input-label { font-size: 0.85rem; color: #cbd5e1; margin-bottom: 8px; display: block; }
                .modern-dropdown { margin-bottom: 20px; }
                
                /* Fixed dropdown styles */
                .modern-dropdown .Select-control { background: white !important; color: #000000 !important; border: 1px solid #e2e8f0 !important; }
                .modern-dropdown .Select-placeholder { color: #000000 !important; }
                .modern-dropdown .Select-value { color: #000000 !important; }
                .modern-dropdown .Select-value-label { color: #000000 !important; }
                .modern-dropdown .Select-input { color: #000000 !important; }
                .modern-dropdown .Select-menu-outer { background: white !important; border: 1px solid #e2e8f0 !important; }
                .modern-dropdown .Select-menu { background: white !important; }
                .modern-dropdown .Select-option { color: #000000 !important; background: white !important; padding: 8px 12px !important; font-weight: 600 !important; }
                .modern-dropdown .Select-option:hover { background: #f1f5f9 !important; color: #000000 !important; }
                .modern-dropdown .Select-option.is-focused { background: #f1f5f9 !important; color: #000000 !important; }
                .modern-dropdown .Select-option.is-selected { background: #3b82f6 !important; color: white !important; }
                .modern-dropdown div[class*="singleValue"] { color: #000000 !important; }
                .modern-dropdown div[class*="option"] { color: #000000 !important; }
                
                .button-grid { display: grid; grid-template-columns: 1fr; gap: 10px; margin-bottom: 30px; }
                .btn-primary { background: linear-gradient(135deg, #10b981, #059669); color: white; border: none; padding: 12px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
                .btn-secondary { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; border: none; padding: 12px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
                .btn-tertiary { background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; border: none; padding: 12px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
                .btn-primary:hover, .btn-secondary:hover, .btn-tertiary:hover { transform: translateY(-1px); }
                .status-section { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 12px; }
                .status-box { }
                .status-item { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.9rem; }
                .status-item span:first-child { opacity: 0.7; }
                .status-item span:last-child { font-weight: 600; }
                
                /* Main Content */
                .main-content { flex: 1; padding: 30px; overflow-y: auto; }
                .main-header { text-align: center; margin-bottom: 30px; }
                .main-title { font-size: 2.5rem; font-weight: 800; color: #1e293b; margin-bottom: 8px; }
                .main-subtitle { font-size: 1.1rem; color: #64748b; margin-bottom: 20px; }
                .badge-container { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }
                .badge { background: linear-gradient(135deg, #ff9900, #ff6600); color: white; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
                
                /* KPI Grid */
                .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
                .kpi-card { background: white; border-radius: 16px; padding: 25px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); transition: all 0.3s ease; display: flex; align-items: center; gap: 20px; }
                .kpi-card:hover { transform: translateY(-4px); box-shadow: 0 8px 30px rgba(0,0,0,0.12); }
                .kpi-icon { font-size: 2.5rem; }
                .kpi-value { font-size: 2rem; font-weight: 700; margin-bottom: 4px; }
                .kpi-label { font-size: 0.9rem; color: #64748b; font-weight: 500; }
                .revenue .kpi-value { color: #10b981; }
                .traffic .kpi-value { color: #3b82f6; }
                .toll .kpi-value { color: #ef4444; }
                .efficiency .kpi-value { color: #f59e0b; }
                
                /* Charts */
                .charts-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px; }
                .chart-card { background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; }
                .chart { }
                
                /* Map */
                .map-section { background: white; border-radius: 16px; padding: 25px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
                .map-title { font-size: 1.3rem; font-weight: 700; color: #1e293b; margin-bottom: 20px; text-align: center; }
                .map-chart { }
                
                /* Responsive */
                @media (max-width: 1200px) {
                    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
                }
                @media (max-width: 768px) {
                    .app-container { flex-direction: column; }
                    .sidebar { width: 100%; }
                    .kpi-grid, .charts-grid { grid-template-columns: 1fr; }
                    .main-title { font-size: 2rem; }
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