import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import time
from datetime import datetime, timedelta
import json
import math
from geopy.distance import geodesic
import warnings
from folium import plugins
import feedparser
import re
from bs4 import BeautifulSoup
warnings.filterwarnings('ignore')

# Page config
st.set_page_config(
    page_title="🌊 Global Tsunami Warning & Simulation System",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .alert-high {
        background-color: rgba(255, 0, 0, 0.1);
        border-left: 5px solid #ff0000;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .alert-medium {
        background-color: rgba(255, 165, 0, 0.1);
        border-left: 5px solid #ffa500;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .alert-low {
        background-color: rgba(255, 255, 0, 0.1);
        border-left: 5px solid #ffff00;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .info-box {
        background-color: rgba(0, 123, 255, 0.1);
        border-left: 5px solid #007bff;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .metric-container {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>🌊 Global Tsunami Warning & Simulation System</h1>
    <p>Real-time monitoring, early warning, and wave propagation simulation</p>
</div>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()
if 'earthquake_data' not in st.session_state:
    st.session_state.earthquake_data = pd.DataFrame()
if 'tsunami_alerts' not in st.session_state:
    st.session_state.tsunami_alerts = []
if 'news_data' not in st.session_state:
    st.session_state.news_data = []

# Sidebar
st.sidebar.title("🔧 Control Panel")
st.sidebar.markdown("---")

# Auto-refresh toggle
auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh data", value=True)
refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 30, 300, 60)

# Manual refresh button
if st.sidebar.button("🔄 Refresh Now"):
    st.session_state.last_update = datetime.now()
    st.rerun()

# Data source selection
st.sidebar.subheader("🌐 Data Sources")
use_usgs = st.sidebar.checkbox("USGS Earthquake API", value=True)
use_noaa = st.sidebar.checkbox("NOAA Tsunami Alerts", value=True)
use_jma = st.sidebar.checkbox("JMA Seismic Data", value=False)
use_news = st.sidebar.checkbox("Live News Feeds", value=True)

# News source selection
if use_news:
    st.sidebar.subheader("📰 News Sources")
    news_sources = st.sidebar.multiselect(
        "Select News Sources",
        ["Reuters", "BBC", "CNN", "AP News", "USGS News", "NOAA News", "Earthquake Alert"],
        default=["Reuters", "BBC", "USGS News"]
    )

# Alert thresholds
st.sidebar.subheader("⚠️ Alert Thresholds")
min_magnitude = st.sidebar.slider("Minimum Earthquake Magnitude", 4.0, 9.0, 6.5, 0.1)
depth_threshold = st.sidebar.slider("Maximum Depth (km)", 10, 700, 100)
tsunami_threshold = st.sidebar.slider("Tsunami Warning Magnitude", 6.0, 9.0, 7.0, 0.1)

# Functions for data fetching
@st.cache_data(ttl=60)
def fetch_usgs_data():
    """Fetch earthquake data from USGS"""
    try:
        # Get earthquakes from last 24 hours
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            earthquakes = []
            
            for feature in data['features']:
                props = feature['properties']
                coords = feature['geometry']['coordinates']
                
                # Validate and clean data
                magnitude = props.get('mag')
                depth = coords[2] if len(coords) > 2 else 0
                
                # Skip invalid entries
                if magnitude is None or magnitude < 0:
                    continue
                if depth is None:
                    depth = 0
                
                earthquake = {
                    'time': pd.to_datetime(props['time'], unit='ms'),
                    'latitude': coords[1],
                    'longitude': coords[0],
                    'depth': max(0, depth),  # Ensure depth is non-negative
                    'magnitude': max(0.1, magnitude),  # Ensure magnitude is positive
                    'place': props.get('place', 'Unknown location'),
                    'alert': props.get('alert', 'green'),
                    'tsunami': props.get('tsunami', 0),
                    'url': props.get('url', ''),
                    'id': feature['id']
                }
                earthquakes.append(earthquake)
            
            df = pd.DataFrame(earthquakes)
            # Additional data cleaning
            if not df.empty:
                df = df.dropna(subset=['magnitude', 'latitude', 'longitude'])
                df = df[df['magnitude'] > 0]  # Remove any remaining invalid magnitudes
            
            return df
    except Exception as e:
        st.error(f"Error fetching USGS data: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_noaa_tsunami_data():
    """Fetch tsunami alert data from NOAA"""
    try:
        # NOAA doesn't have a direct public API, so we'll simulate based on earthquake data
        # In a real implementation, you'd integrate with official tsunami warning systems
        alerts = []
        if not st.session_state.earthquake_data.empty:
            recent_large = st.session_state.earthquake_data[
                (st.session_state.earthquake_data['magnitude'] >= tsunami_threshold) &
                (st.session_state.earthquake_data['depth'] <= depth_threshold) &
                (st.session_state.earthquake_data['time'] >= datetime.now() - timedelta(hours=24))
            ]
            
            for _, eq in recent_large.iterrows():
                # Calculate tsunami threat level
                threat_level = calculate_tsunami_threat(eq['magnitude'], eq['depth'])
                
                alert = {
                    'id': f"tsunami_{eq['id']}",
                    'earthquake_id': eq['id'],
                    'threat_level': threat_level,
                    'magnitude': eq['magnitude'],
                    'location': eq['place'],
                    'latitude': eq['latitude'],
                    'longitude': eq['longitude'],
                    'time': eq['time'],
                    'estimated_arrival': calculate_tsunami_arrival_times(eq['latitude'], eq['longitude'])
                }
                alerts.append(alert)
        
        return alerts
    except Exception as e:
        st.error(f"Error processing tsunami data: {str(e)}")
        return []

def calculate_tsunami_threat(magnitude, depth):
    """Calculate tsunami threat level based on earthquake parameters"""
    if magnitude >= 8.5 and depth <= 50:
        return "EXTREME"
    elif magnitude >= 8.0 and depth <= 70:
        return "HIGH"
    elif magnitude >= 7.5 and depth <= 100:
        return "MEDIUM"
    elif magnitude >= 7.0 and depth <= 150:
        return "LOW"
    else:
        return "MINIMAL"

def calculate_tsunami_arrival_times(eq_lat, eq_lon):
    """Calculate estimated tsunami arrival times for major coastal cities"""
    # Major coastal cities coordinates
    cities = {
        'Honolulu, HI': (21.3099, -157.8581),
        'Los Angeles, CA': (34.0522, -118.2437),
        'San Francisco, CA': (37.7749, -122.4194),
        'Seattle, WA': (47.6062, -122.3321),
        'Tokyo, Japan': (35.6762, 139.6503),
        'Manila, Philippines': (14.5995, 120.9842),
        'Sydney, Australia': (-33.8688, 151.2093),
        'Vladivostok, Russia': (43.1056, 131.8735)
    }
    
    arrival_times = {}
    tsunami_speed = 800  # km/h average speed in deep ocean
    
    for city, (lat, lon) in cities.items():
        distance = geodesic((eq_lat, eq_lon), (lat, lon)).kilometers
        travel_time_hours = distance / tsunami_speed
        arrival_time = datetime.now() + timedelta(hours=travel_time_hours)
        arrival_times[city] = {
            'distance_km': distance,
            'travel_time_hours': travel_time_hours,
            'estimated_arrival': arrival_time
        }
    
    return arrival_times

def simulate_wave_propagation(eq_lat, eq_lon, magnitude, hours_ahead=6):
    """Simulate tsunami wave propagation"""
    # Create a grid for wave simulation
    lat_range = np.linspace(eq_lat - 20, eq_lat + 20, 50)
    lon_range = np.linspace(eq_lon - 30, eq_lon + 30, 50)
    
    simulation_data = []
    tsunami_speed = 800  # km/h
    
    for hour in range(hours_ahead + 1):
        for lat in lat_range[::5]:  # Sample every 5th point for performance
            for lon in lon_range[::5]:
                distance = geodesic((eq_lat, eq_lon), (lat, lon)).kilometers
                travel_time = distance / tsunami_speed
                
                if travel_time <= hour:
                    # Calculate wave height based on magnitude and distance
                    wave_height = max(0, (magnitude - 6) * np.exp(-distance / 2000))
                    if wave_height > 0.1:  # Only include significant waves
                        simulation_data.append({
                            'hour': hour,
                            'latitude': lat,
                            'longitude': lon,
                            'wave_height': wave_height,
                            'distance': distance
                        })
    
    return pd.DataFrame(simulation_data)

# News fetching functions
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_news_feeds():
    """Fetch news from multiple sources"""
    news_feeds = {
        "Reuters": "http://feeds.reuters.com/reuters/topNews",
        "BBC": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "CNN": "http://rss.cnn.com/rss/edition.rss",
        "AP News": "https://feeds.apnews.com/rss/apf-topnews",
        "USGS News": "https://www.usgs.gov/news/news-releases-feed",
        "NOAA News": "https://www.noaa.gov/rss/all-news-rss-feed.xml",
        "Earthquake Alert": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.atom"
    }
    
    all_news = []
    earthquake_keywords = ['earthquake', 'tsunami', 'seismic', 'tremor', 'quake', 'aftershock', 'magnitude', 'richter', 'epicenter']
    
    for source, url in news_feeds.items():
        if source in news_sources:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:  # Get latest 10 articles per source
                    # Check if article is earthquake/tsunami related
                    title_lower = entry.title.lower()
                    summary_lower = entry.get('summary', '').lower()
                    
                    is_relevant = any(keyword in title_lower or keyword in summary_lower 
                                    for keyword in earthquake_keywords)
                    
                    if is_relevant or source in ['USGS News', 'Earthquake Alert']:
                        # Clean HTML from summary
                        summary = entry.get('summary', entry.get('description', ''))
                        if summary:
                            soup = BeautifulSoup(summary, 'html.parser')
                            summary = soup.get_text()
                        
                        news_item = {
                            'source': source,
                            'title': entry.title,
                            'summary': summary[:300] + "..." if len(summary) > 300 else summary,
                            'link': entry.link,
                            'published': entry.get('published', 'No date'),
                            'published_parsed': entry.get('published_parsed'),
                            'relevance_score': calculate_relevance_score(entry.title, summary)
                        }
                        all_news.append(news_item)
            except Exception as e:
                st.warning(f"Could not fetch news from {source}: {str(e)}")
    
    # Sort by relevance and date
    all_news.sort(key=lambda x: (x['relevance_score'], x['published_parsed'] or (0,) * 9), reverse=True)
    return all_news[:50]  # Return top 50 most relevant articles

def calculate_relevance_score(title, summary):
    """Calculate relevance score for earthquake/tsunami news"""
    high_priority_keywords = ['tsunami', 'earthquake', 'magnitude 7', 'magnitude 8', 'magnitude 9', 'warning', 'alert']
    medium_priority_keywords = ['seismic', 'tremor', 'aftershock', 'epicenter', 'richter', 'fault']
    
    text = (title + " " + summary).lower()
    score = 0
    
    for keyword in high_priority_keywords:
        score += text.count(keyword) * 3
    
    for keyword in medium_priority_keywords:
        score += text.count(keyword) * 1
    
    return score

def create_advanced_map(earthquake_data, tsunami_alerts):
    """Create an advanced interactive map with multiple layers"""
    if earthquake_data.empty:
        # Default center if no data
        center_lat, center_lon = 35.0, 139.0
    else:
        center_lat = earthquake_data['latitude'].mean()
        center_lon = earthquake_data['longitude'].mean()
    
    # Create base map with satellite tiles
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=3,
        tiles=None
    )
    
    # Add multiple tile layers
    folium.TileLayer('OpenStreetMap').add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Ocean_Basemap/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Ocean',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Create feature groups for different layers
    earthquake_layer = folium.FeatureGroup(name='Earthquakes')
    tsunami_layer = folium.FeatureGroup(name='Tsunami Alerts')
    plate_boundaries = folium.FeatureGroup(name='Tectonic Plates')
    
    # Add earthquake markers with advanced styling
    if not earthquake_data.empty:
        recent_eq = earthquake_data[earthquake_data['time'] >= datetime.now() - timedelta(hours=24)]
        
        for _, eq in recent_eq.iterrows():
            # Dynamic color and size based on magnitude and time
            age_hours = (datetime.now() - eq['time']).total_seconds() / 3600
            
            if eq['magnitude'] >= 8.0:
                color = '#8B0000'  # Dark red
                radius = 25
                icon = 'exclamation-triangle'
            elif eq['magnitude'] >= 7.0:
                color = '#FF0000'  # Red
                radius = 20
                icon = 'exclamation-sign'
            elif eq['magnitude'] >= 6.0:
                color = '#FF8C00'  # Orange
                radius = 15
                icon = 'warning-sign'
            elif eq['magnitude'] >= 5.0:
                color = '#FFD700'  # Gold
                radius = 10
                icon = 'info-sign'
            else:
                color = '#32CD32'  # Green
                radius = 5
                icon = 'record'
            
            # Fade older earthquakes
            opacity = max(0.3, 1 - (age_hours / 24))
            
            # Create detailed popup
            popup_html = f"""
            <div style="width: 300px;">
                <h4 style="color: {color};">📍 Magnitude {eq['magnitude']:.1f} Earthquake</h4>
                <hr>
                <b>🕐 Time:</b> {eq['time'].strftime('%Y-%m-%d %H:%M:%S UTC')}<br>
                <b>📍 Location:</b> {eq['place']}<br>
                <b>🌊 Depth:</b> {eq['depth']:.1f} km<br>
                <b>⚠️ Tsunami Risk:</b> {'HIGH' if eq['magnitude'] >= 7.0 and eq['depth'] <= 100 else 'LOW'}<br>
                <b>🔗 Details:</b> <a href="{eq.get('url', '#')}" target="_blank">USGS Report</a>
                <hr>
                <small>Age: {age_hours:.1f} hours ago</small>
            </div>
            """
            
            # Add circle marker
            folium.CircleMarker(
                location=[eq['latitude'], eq['longitude']],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=320),
                color='white',
                weight=2,
                fillColor=color,
                fillOpacity=opacity,
                opacity=opacity
            ).add_to(earthquake_layer)
            
            # Add pulsing effect for recent large earthquakes
            if eq['magnitude'] >= 7.0 and age_hours < 6:
                folium.plugins.BeautifyIcon(
                    icon=icon,
                    border_color=color,
                    background_color='white',
                    text_color=color
                ).add_to(earthquake_layer)
    
    # Add tsunami alert zones
    for alert in tsunami_alerts:
        threat_colors = {
            'EXTREME': '#8B0000',
            'HIGH': '#FF0000',
            'MEDIUM': '#FF8C00',
            'LOW': '#FFD700'
        }
        
        color = threat_colors.get(alert['threat_level'], '#32CD32')
        
        # Create expanding circles for different threat levels
        radii = {'EXTREME': [50000, 100000, 200000], 'HIGH': [30000, 80000], 
                'MEDIUM': [20000, 50000], 'LOW': [10000, 30000]}
        
        for i, radius in enumerate(radii.get(alert['threat_level'], [20000])):
            folium.Circle(
                location=[alert['latitude'], alert['longitude']],
                radius=radius,
                popup=f"🌊 {alert['threat_level']} Tsunami Alert\nM{alert['magnitude']:.1f} - {alert['location']}",
                color=color,
                weight=2 - i * 0.5,
                fill=False,
                opacity=0.8 - i * 0.2
            ).add_to(tsunami_layer)
    
    # Add tectonic plate boundaries (simplified)
    plate_boundary_coords = [
        # Pacific Ring of Fire (simplified)
        [[60, -180], [60, -120], [40, -120], [35, -125], [32, -115], [25, -110]],
        [[25, -110], [15, -95], [10, -85], [-10, -80], [-30, -70], [-40, -75]],
        # Japan Trench
        [[45, 145], [40, 142], [35, 140], [30, 138], [25, 135]],
        # Kamchatka-Aleutian
        [[65, 170], [60, 165], [55, 160], [52, 158], [50, 155]]
    ]
    
    for coords in plate_boundary_coords:
        folium.PolyLine(
            coords,
            color='red',
            weight=2,
            opacity=0.6,
            popup="Tectonic Plate Boundary"
        ).add_to(plate_boundaries)
    
    # Add all layers to map
    earthquake_layer.add_to(m)
    tsunami_layer.add_to(m)
    plate_boundaries.add_to(m)
    
    # Add heat map for earthquake density
    if not earthquake_data.empty:
        heat_data = [[row['latitude'], row['longitude'], row['magnitude']] 
                    for _, row in earthquake_data.iterrows()]
        plugins.HeatMap(heat_data, radius=15, blur=10, gradient={
            0.2: 'blue', 0.4: 'lime', 0.6: 'orange', 1: 'red'
        }).add_to(folium.FeatureGroup(name='Earthquake Heatmap').add_to(m))
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(m)
    
    # Add measure tool
    plugins.MeasureControl().add_to(m)
    
    # Add mouse position
    plugins.MousePosition().add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    return m

# Main data fetching
if auto_refresh and (datetime.now() - st.session_state.last_update).seconds > refresh_interval:
    st.session_state.last_update = datetime.now()
    st.rerun()

# Fetch earthquake data
if use_usgs:
    with st.spinner("🌍 Fetching earthquake data..."):
        st.session_state.earthquake_data = fetch_usgs_data()

# Process tsunami alerts
if use_noaa and not st.session_state.earthquake_data.empty:
    with st.spinner("🌊 Processing tsunami alerts..."):
        st.session_state.tsunami_alerts = fetch_noaa_tsunami_data()

# Fetch news data
if use_news:
    with st.spinner("📰 Fetching latest news..."):
        st.session_state.news_data = fetch_news_feeds()

# Main dashboard layout
col1, col2, col3, col4 = st.columns(4)

# Display key metrics
if not st.session_state.earthquake_data.empty:
    recent_eq = st.session_state.earthquake_data[
        st.session_state.earthquake_data['time'] >= datetime.now() - timedelta(hours=24)
    ]
    
    with col1:
        st.markdown(f'''
        <div class="metric-container">
            <h3 style="margin-bottom:0.5em;">🌍 Earthquakes (24h)</h3>
            <div style="font-size:2em;font-weight:bold;">{len(recent_eq)}</div>
        </div>
        ''', unsafe_allow_html=True)
    
    with col2:
        large_eq = recent_eq[recent_eq['magnitude'] >= min_magnitude]
        st.markdown(f'''
        <div class="metric-container">
            <h3 style="margin-bottom:0.5em;">⚡ Magnitude ≥{min_magnitude}</h3>
            <div style="font-size:2em;font-weight:bold;">{len(large_eq)}</div>
        </div>
        ''', unsafe_allow_html=True)
    with col3:
        tsunami_risk = recent_eq[
            (recent_eq['magnitude'] >= tsunami_threshold) & 
            (recent_eq['depth'] <= depth_threshold)
        ]
        st.markdown(f'''
        <div class="metric-container">
            <h3 style="margin-bottom:0.5em;">🌊 Tsunami Risk</h3>
            <div style="font-size:2em;font-weight:bold;">{len(tsunami_risk)}</div>
        </div>
        ''', unsafe_allow_html=True)
    
    with col4:
        max_mag = recent_eq['magnitude'].max() if not recent_eq.empty else 0
        st.markdown(f'''
        <div class="metric-container">
            <h3 style="margin-bottom:0.5em;">📊 Max Magnitude</h3>
            <div style="font-size:2em;font-weight:bold;">{max_mag:.1f}</div>
        </div>
        ''', unsafe_allow_html=True)

# Current Alerts Section
st.subheader("🚨 Current Tsunami Alerts")

if st.session_state.tsunami_alerts:
    for alert in st.session_state.tsunami_alerts:
        threat_level = alert['threat_level']
        
        if threat_level == "EXTREME":
            alert_class = "alert-high"
            icon = "🔴"
        elif threat_level == "HIGH":
            alert_class = "alert-high"
            icon = "🟠"
        elif threat_level == "MEDIUM":
            alert_class = "alert-medium"
            icon = "🟡"
        else:
            alert_class = "alert-low"
            icon = "🟢"
        
        st.markdown(f"""
        <div class="{alert_class}">
            <h4>{icon} {threat_level} TSUNAMI THREAT</h4>
            <p><strong>Location:</strong> {alert['location']}</p>
            <p><strong>Magnitude:</strong> {alert['magnitude']:.1f}</p>
            <p><strong>Time:</strong> {alert['time'].strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Show arrival times
        if alert['estimated_arrival']:
            st.subheader("⏰ Estimated Arrival Times")
            arrival_df = pd.DataFrame([
                {
                    'City': city,
                    'Distance (km)': data['distance_km'],
                    'Travel Time (hours)': f"{data['travel_time_hours']:.1f}",
                    'Estimated Arrival': data['estimated_arrival'].strftime('%Y-%m-%d %H:%M UTC')
                }
                for city, data in alert['estimated_arrival'].items()
            ]).sort_values('Distance (km)')
            
            st.dataframe(arrival_df, use_container_width=True)
else:
    st.markdown("""
    <div class="info-box">
        <h4>ℹ️ No Active Tsunami Alerts</h4>
        <p>Currently monitoring for seismic activity. System will automatically generate alerts based on earthquake parameters.</p>
    </div>
    """, unsafe_allow_html=True)

# Tabs for different views
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗺️ Advanced Map", "📰 Live News", "📊 Analytics", "🌊 Simulation", "📋 Recent Events"])

with tab1:
    st.subheader("🗺️ Advanced Interactive Earthquake & Tsunami Map")
    
    if not st.session_state.earthquake_data.empty:
        # Map controls
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            show_heatmap = st.checkbox("🔥 Earthquake Heatmap", value=True)
        with col2:
            show_plates = st.checkbox("🌋 Tectonic Plates", value=True)
        with col3:
            time_filter = st.selectbox("⏰ Time Filter", ["Last 24 hours", "Last 7 days", "Last 30 days"])
        with col4:
            min_mag_map = st.slider("🎚️ Min Magnitude", 0.0, 8.0, 4.0, 0.5)
        
        # Filter data based on controls
        time_deltas = {
            "Last 24 hours": timedelta(hours=24),
            "Last 7 days": timedelta(days=7),
            "Last 30 days": timedelta(days=30)
        }
        
        filtered_data = st.session_state.earthquake_data[
            (st.session_state.earthquake_data['time'] >= datetime.now() - time_deltas[time_filter]) &
            (st.session_state.earthquake_data['magnitude'] >= min_mag_map)
        ]
        
        # Create and display advanced map
        advanced_map = create_advanced_map(filtered_data, st.session_state.tsunami_alerts)
        
        # Display map with custom height and prevent auto-reload on interaction
        map_data = st_folium(
            advanced_map, 
            width=None, 
            height=600,
            returned_objects=["last_object_clicked"],
            key="main_map"  # Stable key prevents unnecessary reloads
        )
        
        # Display clicked earthquake info in a compact way
        if map_data.get('last_object_clicked'):
            clicked_data = map_data['last_object_clicked']
            if clicked_data and 'lat' in clicked_data and 'lng' in clicked_data:
                # Find closest earthquake to clicked point
                click_lat, click_lng = clicked_data['lat'], clicked_data['lng']
                if not filtered_data.empty:
                    distances = filtered_data.apply(
                        lambda row: geodesic((click_lat, click_lng), (row['latitude'], row['longitude'])).kilometers,
                        axis=1
                    )
                    closest_idx = distances.idxmin()
                    closest_eq = filtered_data.loc[closest_idx]
                    
                    if distances[closest_idx] < 100:  # Within 100km
                        with st.container():
                            st.info(f"📍 **Selected Earthquake:** M{closest_eq['magnitude']:.1f} - {closest_eq['place']} ({closest_eq['time'].strftime('%Y-%m-%d %H:%M')})")
                            
                            # Show additional details in expandable section
                            with st.expander("🔍 View Full Details"):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.write(f"**Magnitude:** {closest_eq['magnitude']:.1f}")
                                    st.write(f"**Depth:** {closest_eq['depth']:.1f} km")
                                with col2:
                                    st.write(f"**Coordinates:** {closest_eq['latitude']:.2f}, {closest_eq['longitude']:.2f}")
                                    tsunami_risk = 'HIGH' if closest_eq['magnitude'] >= 7.0 and closest_eq['depth'] <= 100 else 'LOW'
                                    st.write(f"**Tsunami Risk:** {tsunami_risk}")
                                with col3:
                                    st.write(f"**Time:** {closest_eq['time'].strftime('%Y-%m-%d %H:%M:%S')}")
                                    if closest_eq.get('url'):
                                        st.markdown(f"[📋 USGS Report]({closest_eq['url']})")
                    else:
                        st.info("👆 Click on an earthquake marker to see details")
        
        # Map statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📍 Earthquakes Shown", len(filtered_data))
        with col2:
            avg_mag = filtered_data['magnitude'].mean() if not filtered_data.empty else 0
            st.metric("📊 Average Magnitude", f"{avg_mag:.1f}")
        with col3:
            max_mag = filtered_data['magnitude'].max() if not filtered_data.empty else 0
            st.metric("🔥 Strongest Event", f"M{max_mag:.1f}")
        with col4:
            tsunami_count = len([a for a in st.session_state.tsunami_alerts if a['threat_level'] in ['HIGH', 'EXTREME']])
            st.metric("🌊 Active Alerts", tsunami_count)
            
    else:
        st.info("🔄 Loading earthquake data... Please check your internet connection if this persists.")

with tab2:
    st.subheader("📰 Breaking News & Updates")
    
    if st.session_state.news_data:
        # News filters
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_sources = st.multiselect(
                "Filter by Source",
                options=list(set([news['source'] for news in st.session_state.news_data])),
                default=list(set([news['source'] for news in st.session_state.news_data]))
            )
        with col2:
            sort_by = st.selectbox("Sort by", ["Relevance", "Date", "Source"])
        with col3:
            max_articles = st.slider("Max Articles", 5, 50, 20)
        
        # Filter and sort news
        filtered_news = [news for news in st.session_state.news_data if news['source'] in selected_sources]
        
        if sort_by == "Date":
            filtered_news.sort(key=lambda x: x['published_parsed'] or (0,) * 9, reverse=True)
        elif sort_by == "Source":
            filtered_news.sort(key=lambda x: x['source'])
        # Relevance is already sorted
        
        filtered_news = filtered_news[:max_articles]
        
        # Display news in cards
        for i, news in enumerate(filtered_news):
            with st.container():
                # Color coding by source
                source_colors = {
                    'Reuters': '#FF6B35',
                    'BBC': '#BB1919',
                    'CNN': '#CC0000',
                    'AP News': '#0077C8',
                    'USGS News': '#006633',
                    'NOAA News': '#003366',
                    'Earthquake Alert': '#8B0000'
                }
                
                color = source_colors.get(news['source'], '#666666')
                
                st.markdown(f"""
                <div style="
                    border-left: 5px solid {color}; 
                    padding: 15px; 
                    margin: 10px 0; 
                    background-color: rgba(255, 255, 255, 0.05);
                    border-radius: 5px;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span style="background-color: {color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                            {news['source']}
                        </span>
                        <small style="color: #888;">{news['published']}</small>
                    </div>
                    <h4 style="margin: 8px 0; color: {color};">
                        <a href="{news['link']}" target="_blank" style="text-decoration: none; color: inherit;">
                            {news['title']}
                        </a>
                    </h4>
                    <p style="margin: 8px 0; line-height: 1.5; color: #ddd;">
                        {news['summary']}
                    </p>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                        <span style="background-color: rgba({color[1:3]}, {color[3:5]}, {color[5:7]}, 0.2); 
                                     color: {color}; padding: 2px 6px; border-radius: 8px; font-size: 11px;">
                            Relevance: {news['relevance_score']}
                        </span>
                        <a href="{news['link']}" target="_blank" style="
                            background-color: {color}; 
                            color: white; 
                            padding: 5px 12px; 
                            border: none; 
                            border-radius: 15px; 
                            text-decoration: none; 
                            font-size: 12px;
                            font-weight: bold;
                        ">
                            Read Full Article →
                        </a>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Add separator
                if i < len(filtered_news) - 1:
                    st.markdown("<hr style='margin: 20px 0; opacity: 0.3;'>", unsafe_allow_html=True)
        
        # News summary statistics
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📰 Total Articles", len(st.session_state.news_data))
        with col2:
            sources_count = len(set([news['source'] for news in st.session_state.news_data]))
            st.metric("📡 Active Sources", sources_count)
        with col3:
            high_relevance = len([news for news in st.session_state.news_data if news['relevance_score'] > 5])
            st.metric("🔥 High Priority", high_relevance)
        with col4:
            recent_count = len([news for news in st.session_state.news_data 
                              if news['published_parsed'] and 
                              datetime(*news['published_parsed'][:6]) > datetime.now() - timedelta(hours=6)])
            st.metric("⏰ Last 6 Hours", recent_count)
            
    else:
        st.info("📡 Loading latest news feeds... This may take a moment.")
        
        # Show loading placeholders
        for i in range(3):
            with st.container():
                st.markdown(f"""
                <div style="
                    border-left: 5px solid #666; 
                    padding: 15px; 
                    margin: 10px 0; 
                    background-color: rgba(255, 255, 255, 0.02);
                    border-radius: 5px;
                    opacity: 0.5;
                ">
                    <div style="height: 20px; background-color: rgba(255, 255, 255, 0.1); border-radius: 4px; margin-bottom: 10px;"></div>
                    <div style="height: 60px; background-color: rgba(255, 255, 255, 0.05); border-radius: 4px;"></div>
                </div>
                """, unsafe_allow_html=True)

with tab3:
    st.subheader("📊 Seismic Activity Analytics")
    
    if not st.session_state.earthquake_data.empty:
        recent_data = st.session_state.earthquake_data[
            st.session_state.earthquake_data['time'] >= datetime.now() - timedelta(days=7)
        ]
        
        if not recent_data.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Clean data for visualization
                clean_data = recent_data.dropna(subset=['magnitude', 'depth'])
                clean_data = clean_data[
                    (clean_data['magnitude'] > 0) & 
                    (clean_data['depth'] >= 0) & 
                    (clean_data['magnitude'] <= 10)  # Remove outliers
                ]
                
                if not clean_data.empty:
                    # Magnitude distribution
                    fig_mag = px.histogram(
                        clean_data, 
                        x='magnitude', 
                        nbins=20,
                        title="Magnitude Distribution (Last 7 Days)",
                        color_discrete_sequence=['#1f77b4']
                    )
                    fig_mag.update_layout(height=400)
                    st.plotly_chart(fig_mag, use_container_width=True)
                    
                    # Depth vs Magnitude scatter
                    # Ensure size values are positive and reasonable
                    clean_data['size_val'] = np.maximum(clean_data['magnitude'], 0.1) * 3  # Scale for visibility
                    
                    fig_scatter = px.scatter(
                        clean_data,
                        x='depth',
                        y='magnitude',
                        color='magnitude',
                        size='size_val',
                        title="Depth vs Magnitude",
                        hover_data=['place', 'time'],
                        size_max=20
                    )
                    fig_scatter.update_layout(height=400)
                    st.plotly_chart(fig_scatter, use_container_width=True)
                else:
                    st.warning("No valid data available for magnitude analysis.")
            
            with col2:
                if not clean_data.empty:
                    # Time series
                    daily_counts = clean_data.groupby(clean_data['time'].dt.date).size().reset_index()
                    daily_counts.columns = ['date', 'count']
                    
                    fig_time = px.line(
                        daily_counts,
                        x='date',
                        y='count',
                        title="Daily Earthquake Count",
                        markers=True
                    )
                    fig_time.update_layout(height=400)
                    st.plotly_chart(fig_time, use_container_width=True)
                    
                    # Alert level distribution - only for valid data
                    clean_data['alert_level'] = clean_data.apply(
                        lambda x: calculate_tsunami_threat(x['magnitude'], x['depth']), axis=1
                    )
                    
                    alert_counts = clean_data['alert_level'].value_counts()
                    if not alert_counts.empty:
                        fig_alerts = px.pie(
                            values=alert_counts.values,
                            names=alert_counts.index,
                            title="Tsunami Threat Levels"
                        )
                        fig_alerts.update_layout(height=400)
                        st.plotly_chart(fig_alerts, use_container_width=True)
                    else:
                        st.warning("No threat level data available.")
                else:
                    st.warning("No valid data available for time series analysis.")
    else:
        st.info("No data available for analytics.")

with tab4:
    st.subheader("🌊 Tsunami Wave Propagation Simulation")
    
    # Simulation controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sim_lat = st.number_input("Earthquake Latitude", value=56.0, min_value=-90.0, max_value=90.0)
    with col2:
        sim_lon = st.number_input("Earthquake Longitude", value=164.0, min_value=-180.0, max_value=180.0)
    with col3:
        sim_magnitude = st.slider("Earthquake Magnitude", 6.0, 9.0, 8.8, 0.1)
    
    hours_to_simulate = st.slider("Hours to simulate", 1, 12, 6)
    
    if st.button("🚀 Run Simulation", type="primary"):
        with st.spinner("Running tsunami propagation simulation..."):
            simulation_data = simulate_wave_propagation(sim_lat, sim_lon, sim_magnitude, hours_to_simulate)
            
            if not simulation_data.empty:
                # Create animation frames
                frames = []
                for hour in range(hours_to_simulate + 1):
                    hour_data = simulation_data[simulation_data['hour'] == hour]
                    if not hour_data.empty:
                        frame = go.Scattergeo(
                            lon=hour_data['longitude'],
                            lat=hour_data['latitude'],
                            mode='markers',
                            marker=dict(
                                size=hour_data['wave_height'] * 10,
                                color=hour_data['wave_height'],
                                colorscale='Blues',
                                cmin=0,
                                cmax=simulation_data['wave_height'].max(),
                                showscale=True,
                                colorbar=dict(title="Wave Height (m)")
                            ),
                            text=hour_data['wave_height'].round(2),
                            hovertemplate='<b>Wave Height:</b> %{text} m<br>' +
                                        '<b>Lat:</b> %{lat}<br>' +
                                        '<b>Lon:</b> %{lon}<extra></extra>',
                            name=f'Hour {hour}'
                        )
                        frames.append(frame)
                
                # Create the plot
                fig = go.Figure()
                
                # Add earthquake epicenter
                fig.add_trace(go.Scattergeo(
                    lon=[sim_lon],
                    lat=[sim_lat],
                    mode='markers',
                    marker=dict(size=20, color='red', symbol='star'),
                    name='Earthquake Epicenter',
                    hovertemplate=f'<b>Magnitude:</b> {sim_magnitude}<br>' +
                                f'<b>Location:</b> ({sim_lat}, {sim_lon})<extra></extra>'
                ))
                
                # Add initial frame
                if frames:
                    fig.add_trace(frames[0])
                
                fig.update_layout(
                    title=f"Tsunami Wave Propagation Simulation (M{sim_magnitude})",
                    geo=dict(
                        projection_type='natural earth',
                        showland=True,
                        landcolor='lightgray',
                        showocean=True,
                        oceancolor='lightblue'
                    ),
                    height=600
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Show simulation summary
                st.subheader("📊 Simulation Summary")
                max_wave = simulation_data['wave_height'].max()
                affected_area = len(simulation_data[simulation_data['wave_height'] > 0.5])
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Max Wave Height", f"{max_wave:.2f} m")
                with col2:
                    st.metric("Affected Grid Points", affected_area)
                with col3:
                    st.metric("Simulation Duration", f"{hours_to_simulate} hours")
            else:
                st.warning("No significant waves generated in simulation.")

with tab5:
    st.subheader("📋 Recent Earthquake Events")
    
    if not st.session_state.earthquake_data.empty:
        # Filter and sort recent events
        recent_events = st.session_state.earthquake_data[
            st.session_state.earthquake_data['time'] >= datetime.now() - timedelta(hours=48)
        ].sort_values('time', ascending=False)
        
        if not recent_events.empty:
            # Add tsunami risk assessment
            recent_events['tsunami_risk'] = recent_events.apply(
                lambda x: 'HIGH' if x['magnitude'] >= tsunami_threshold and x['depth'] <= depth_threshold
                else 'MEDIUM' if x['magnitude'] >= 6.5 and x['depth'] <= depth_threshold
                else 'LOW', axis=1
            )
            
            # Display table
            display_columns = ['time', 'magnitude', 'depth', 'place', 'tsunami_risk']
            display_df = recent_events[display_columns].copy()
            display_df['time'] = display_df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
            display_df.columns = ['Time (UTC)', 'Magnitude', 'Depth (km)', 'Location', 'Tsunami Risk']
            
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "Tsunami Risk": st.column_config.TextColumn(
                        "Tsunami Risk",
                        help="Risk assessment based on magnitude and depth"
                    )
                }
            )
            
            # Export options
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"earthquake_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No recent earthquake events found.")
    else:
        st.info("No earthquake data available.")

# Footer with system status
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.write(f"🕐 Last Update: {st.session_state.last_update.strftime('%H:%M:%S')}")
with col2:
    status_color = "🟢" if not st.session_state.earthquake_data.empty else "🟡"
    st.write(f"{status_color} System Status: {'Online' if not st.session_state.earthquake_data.empty else 'Limited'}")
with col3:
    sources = "USGS"
    if use_noaa: sources += "+NOAA"
    if use_news: sources += "+News"
    st.write(f"📡 Data Sources: {sources}")
with col4:
    news_count = len(st.session_state.news_data) if st.session_state.news_data else 0
    st.write(f"📰 News Articles: {news_count}")

# Auto-refresh functionality - only refresh based on time interval, not map clicks
if auto_refresh and (datetime.now() - st.session_state.last_update).seconds > refresh_interval:
    # Only rerun if 60 seconds have passed since last update
    if (datetime.now() - st.session_state.last_update).seconds >= 60:
        st.session_state.last_update = datetime.now()
        st.rerun()