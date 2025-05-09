# dashboard.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
import plotly.express as px
import time
import sys
import math
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# Configuration
API_BASE_URL = Config.API_BASE_URL
REFRESH_INTERVAL = 60  # seconds

# Page configuration
st.set_page_config(
    page_title="Weather Station Dashboard",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
     .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        height: 150px; /* Fixed height for all metric boxes */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    /* Make custom comfort display match metric style */
    .comfort-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        height: 150px; /* Match metric box height */
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .plot-container {
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 10px;
        background-color: white;
    }
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-online {
        background-color: #28a745;
    }
    .status-offline {
        background-color: #dc3545;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def fetch_data(endpoint: str, params: dict = None):
    """Fetch data from API endpoint"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        st.sidebar.write(f"Fetching from: {url}")
        st.sidebar.write(f"Params: {params}")
        
        response = requests.get(url, params=params, timeout=5)
        st.sidebar.write(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            st.sidebar.write("Response Data:", data)
            return data
        else:
            st.error(f"Error fetching data: {response.status_code}")
            st.error(f"Response: {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        st.sidebar.write(f"Error details: {str(e)}")
        return None

# Add these functions near the top of your dashboard.py file
def calculate_heat_index(temperature, humidity):
    """Calculate heat index (feels like temperature) in Celsius"""
    # Convert to Fahrenheit for the standard heat index formula
    temp_f = temperature * 9/5 + 32
    
    # Simplified heat index formula
    hi = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (humidity * 0.094))
    
    # Use more complex formula if conditions warrant
    if hi > 80:
        hi = -42.379 + 2.04901523 * temp_f + 10.14333127 * humidity
        hi = hi - 0.22475541 * temp_f * humidity
        hi = hi - 0.00683783 * temp_f * temp_f
        hi = hi - 0.05481717 * humidity * humidity
        hi = hi + 0.00122874 * temp_f * temp_f * humidity
        hi = hi + 0.00085282 * temp_f * humidity * humidity
        hi = hi - 0.00000199 * temp_f * temp_f * humidity * humidity
    
    # Convert back to Celsius
    return (hi - 32) * 5/9

def calculate_dew_point(temperature, humidity):
    """Calculate dew point in Celsius using Magnus formula"""
    # Constants for Magnus formula
    a = 17.27
    b = 237.7
    
    # Calculate alpha
    alpha = ((a * temperature) / (b + temperature)) + math.log(humidity/100.0)
    
    # Calculate dew point
    return (b * alpha) / (a - alpha)

def get_comfort_level(temperature, humidity):
    """Determine comfort level based on temperature and humidity"""
    if temperature < 15:
        return "Cold"
    elif temperature < 20:
        if humidity < 40:
            return "Cool & Dry"
        elif humidity < 60:
            return "Cool & Comfortable"
        else:
            return "Cool & Humid"
    elif temperature < 26:
        if humidity < 40:
            return "Comfortable & Dry"
        elif humidity < 60:
            return "Ideal Comfort"
        else:
            return "Comfortable but Humid"
    elif temperature < 30:
        if humidity < 40:
            return "Warm & Dry"
        elif humidity < 60:
            return "Warm & Comfortable"
        else:
            return "Warm & Humid"
    else:
        if humidity < 40:
            return "Hot & Dry"
        elif humidity < 60:
            return "Hot"
        else:
            return "Hot & Sticky"
        
def get_device_status(last_update):
    """Check if device is online based on last update time"""
    # For the ESP32 demo, we'll simply check if we've received data
    # in the past few minutes (absolute time difference)
    ONLINE_TIMEOUT_SECONDS = 180  # 3 minutes - increased for reliability
    
    if not last_update:
        st.sidebar.write("No timestamp available")
        return False
    
    try:
        # Parse the timestamp from API
        if 'Z' in last_update:
            last_update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
        else:
            last_update_time = datetime.fromisoformat(last_update)
            
        # Current time
        current_time = datetime.now(timezone.utc)
        
        # Convert to UNIX timestamps for comparison (seconds since epoch)
        last_update_unix = last_update_time.timestamp()
        current_unix = current_time.timestamp()
        
        # Time difference in seconds (absolute value)
        time_diff = abs(current_unix - last_update_unix)
        
        st.sidebar.write(f"Last data received: {last_update_time.strftime('%H:%M:%S')}")
        st.sidebar.write(f"Time since last update: {int(time_diff)} seconds")
        
        # Simple test - if we unplugged the device, manually set to offline
        # Remove this in production - just for testing
        if time_diff > ONLINE_TIMEOUT_SECONDS:
            st.sidebar.write("⚠️ Device appears to be offline")
            return False
        else:
            st.sidebar.write("✅ Device is online")
            return True
            
    except Exception as e:
        st.sidebar.write(f"Status check error: {str(e)}")
        return False
    
def main():
    st.title("🌡️ Weather Station Dashboard")
    
    # Sidebar debug info
    st.sidebar.header("Debug Information")
    st.sidebar.write(f"API Base URL: {API_BASE_URL}")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        
        # Device selection
        device_id = st.selectbox(
            "Select Device",
            ["ESP32_001", "ESP32_002", "ESP32_003"],
            index=0
        )
        
        # Time range selection
        time_range = st.selectbox(
            "Time Range",
            ["Last Hour", "Last 24 Hours", "Last 7 Days", "Last 30 Days"],
            index=1
        )
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        
        if auto_refresh:
            st.info(f"Dashboard will refresh every {REFRESH_INTERVAL} seconds")
        
        # Manual refresh button
        if st.button("🔄 Refresh Now"):
            st.rerun()
    
    # Fetch latest data
    latest_data = fetch_data("/sensor/latest", {"device_id": device_id})
    
    # Debug: Show raw response
    with st.expander("Debug: Raw API Response"):
        st.json(latest_data)
    
    # Display current readings
    if latest_data and latest_data.get('status') == 'success' and 'data' in latest_data:
        data = latest_data['data']
        
        # Device status
        is_online = get_device_status(data.get('timestamp'))
        status_class = "status-online" if is_online else "status-offline"
        status_text = "Online" if is_online else "Offline"
        
        st.markdown(f"""
        <h3>
            <span class="status-indicator {status_class}"></span>
            Device Status: {status_text}
        </h3>
        """, unsafe_allow_html=True)
        
        # Current readings
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="🌡️ Temperature",
                value=f"{data['temperature']:.1f}°C",
                delta=None
            )
        
        with col2:
            st.metric(
                label="💧 Humidity",
                value=f"{data['humidity']:.1f}%",
                delta=None
            )
        
        with col3:
            if data.get('timestamp'):
                try:
                    last_update_time = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                    st.metric(
                        label="🕒 Last Update",
                        value=last_update_time.strftime('%H:%M:%S'),
                        delta=None
                    )
                except Exception as e:
                    st.metric(
                        label="🕒 Last Update",
                        value="Error parsing time",
                        delta=None
                    )
                    st.sidebar.write(f"Time parse error: {str(e)}")
            else:
                st.metric(
                    label="🕒 Last Update",
                    value="No timestamp",
                    delta=None
                )
                
        # Add calculated metrics in a new row
        st.subheader("Calculated Metrics")
        
        # Calculate derived metrics
        try:
            temp = float(data['temperature'])
            humidity = float(data['humidity'])
            
            heat_index = calculate_heat_index(temp, humidity)
            dew_point = calculate_dew_point(temp, humidity)
            comfort = get_comfort_level(temp, humidity)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    label="🔥 Feels Like",
                    value=f"{heat_index:.1f}°C",
                    delta=round(heat_index - temp, 1),
                    delta_color="off"
                )
            
            with col2:
                st.metric(
                    label="💦 Dew Point",
                    value=f"{dew_point:.1f}°C",
                    delta=None
                )
            
            with col3:
                # Style comfort level based on its value
                comfort_color = ""
                if "Cold" in comfort or "Hot" in comfort:
                    comfort_color = "color: orange;"
                elif "Ideal" in comfort:
                    comfort_color = "color: green;"
                    
                st.markdown(f"""
                <div class="comfort-box">
        <p style="font-size: 0.8rem; margin-bottom: 5px;">COMFORT LEVEL</p>
        <p style="font-size: 1.3rem; font-weight: bold; margin: 0; {comfort_color}">{comfort}</p>
    </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"Error calculating metrics: {str(e)}")
    else:
        st.warning("No data available")
        st.write("Response structure:", latest_data)
    
    st.divider()
    
    # Historical data
    st.header("Historical Data")
    
    # Map time range to API parameters
    time_range_map = {
        "Last Hour": {"period": "1h", "limit": 60},
        "Last 24 Hours": {"period": "24h", "limit": 288},
        "Last 7 Days": {"period": "7d", "limit": 2016},
        "Last 30 Days": {"period": "30d", "limit": 8640}
    }
    
    params = time_range_map.get(time_range, {"period": "24h", "limit": 288})
    params["device_id"] = device_id
    
    # Fetch historical data
    historical_data = fetch_data("/sensor/history", params)
    
    if historical_data and historical_data.get('status') == 'success' and historical_data.get('data'):
        df = pd.DataFrame(historical_data['data'])
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Temperature chart
            fig_temp = go.Figure()
            fig_temp.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['temperature'],
                mode='lines',
                name='Temperature',
                line=dict(color='#FF6B6B', width=2)
            ))
            fig_temp.update_layout(
                title='Temperature Over Time',
                xaxis_title='Time',
                yaxis_title='Temperature (°C)',
                template='plotly_white',
                height=400
            )
            st.plotly_chart(fig_temp, use_container_width=True)
            
            # Humidity chart
            fig_humid = go.Figure()
            fig_humid.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['humidity'],
                mode='lines',
                name='Humidity',
                line=dict(color='#4ECDC4', width=2)
            ))
            fig_humid.update_layout(
                title='Humidity Over Time',
                xaxis_title='Time',
                yaxis_title='Humidity (%)',
                template='plotly_white',
                height=400
            )
            st.plotly_chart(fig_humid, use_container_width=True)
            
            # Statistics
            st.header("Statistics")
            
            stats_data = fetch_data("/sensor/stats", {"device_id": device_id, "period": params["period"]})
            
            if stats_data and stats_data.get('status') == 'success' and 'stats' in stats_data:
                stats = stats_data['stats']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Temperature Statistics")
                    st.write(f"**Minimum:** {stats['temperature']['min']:.1f}°C")
                    st.write(f"**Maximum:** {stats['temperature']['max']:.1f}°C")
                    st.write(f"**Average:** {stats['temperature']['avg']:.1f}°C")
                
                with col2:
                    st.subheader("Humidity Statistics")
                    st.write(f"**Minimum:** {stats['humidity']['min']:.1f}%")
                    st.write(f"**Maximum:** {stats['humidity']['max']:.1f}%")
                    st.write(f"**Average:** {stats['humidity']['avg']:.1f}%")
                
                st.write(f"**Data Points:** {stats['data_points']}")
            else:
                st.info("Statistics not available")
        else:
            st.info("No data available for charts")
    else:
        st.info("No historical data available for the selected time range")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.rerun()
        
if __name__ == "__main__":
    main()