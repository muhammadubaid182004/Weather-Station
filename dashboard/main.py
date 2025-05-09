# main.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
import plotly.express as px
import plotly.graph_objects as go
import base64
import os
from config import Config

# Page config
st.set_page_config(
    page_title="Weather Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configuration
API_BASE_URL = Config.API_BASE_URL

# Function to encode image to base64
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        # Silent error handling for production
        return ""

# Load background and toggle images
try:
    night_bg = get_image_base64("attached_assets/image_1741074776844.png")
    day_bg = get_image_base64("attached_assets/image_1741074670988.png")
    night_toggle = get_image_base64("attached_assets/image_1741161144588.png")
    day_toggle = get_image_base64("attached_assets/image_1741161154037.png")
except Exception as e:
    # Silent error for production
    night_bg = day_bg = night_toggle = day_toggle = ""

# Initialize session state for theme and data
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'current_temp' not in st.session_state:
    st.session_state.current_temp = 0.0
if 'current_humid' not in st.session_state:
    st.session_state.current_humid = 0.0
if 'last_live_temp' not in st.session_state:
    st.session_state.last_live_temp = 0.0
if 'last_live_humid' not in st.session_state:
    st.session_state.last_live_humid = 0.0
if 'df' not in st.session_state:
    st.session_state.df = None
if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = datetime.now()

# Load weather data - Silent version for production
def load_csv_data():
    try:
        # Try to load the CSV file directly without printing debugging info
        if os.path.exists('weather_data.csv'):
            df = pd.read_csv('weather_data.csv')
            
            # Validate DataFrame
            if df.empty:
                st.error("CSV file is empty.")
                return None
            
            # Check required columns
            required_columns = ['date', 'temperature', 'humidity', 'updates']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"Missing columns in CSV: {missing_columns}")
                return None
            
            # Convert date column
            df['date'] = pd.to_datetime(df['date'])
            # Format date as string for display purposes
            df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
            
            return df
        else:
            st.error("Could not find weather_data.csv file.")
            return None
    
    except Exception as e:
        st.error(f"Error loading CSV data: {e}")
        return None

# Fetch live data from Flask server
def fetch_live_data():
    try:
        # Use API_BASE_URL from config
        response = requests.get(f"{API_BASE_URL}/sensor/latest", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                # Store successful live data fetch as last known good values
                st.session_state.last_live_temp = data['data']['temperature']
                st.session_state.last_live_humid = data['data']['humidity']
                # Update the current temperature and humidity values directly
                st.session_state.current_temp = data['data']['temperature']
                st.session_state.current_humid = data['data']['humidity']
                # Update the last update time immediately on successful fetch
                st.session_state.last_update_time = datetime.now()
                return data['data']
            return None
        else:
            # Log error but don't display to user
            print(f"Error fetching live data: {response.status_code}")
            return None
    except Exception as e:
        # Log error but don't display to user
        print(f"Exception when fetching live data: {str(e)}")
        return None


# Function to update data (without threading)
def update_data_once():
    # Try to fetch live data first
    live_data = fetch_live_data()
    if live_data:
        # Live data update is already handled in fetch_live_data()
        pass
    else:
        # Use last successful live data fetch as fallback
        st.session_state.current_temp = st.session_state.last_live_temp
        st.session_state.current_humid = st.session_state.last_live_humid
    
    # Load CSV data for historical data and predictions
    csv_df = load_csv_data()
    if csv_df is not None:
        # Store the full CSV data for visualization and ML predictions
        st.session_state.df = csv_df

# Toggle theme callback - separate from main UI to prevent full page rerun
def toggle_theme():
    st.session_state.dark_mode = not st.session_state.dark_mode
    # Don't call st.rerun() here to prevent page refresh

# Apply background and theme based on mode
def get_background_style():
    return f"""
    <style>
        .stApp {{
            background-image: url("data:image/png;base64,{night_bg if st.session_state.dark_mode else day_bg}");
            background-size: cover !important;
            background-position: center !important;
            min-height: 100vh;
            transition: all 0.3s ease-in-out;
        }}
        :root {{
            --text-color: {('#f0f2f6' if st.session_state.dark_mode else '#262730')};
            --toggle-bg: {('#4d2c72' if st.session_state.dark_mode else '#4d7df8')};
            --toggle-text: {('#f5e3ff' if st.session_state.dark_mode else '#ffffff')};
        }}
    </style>
    """

# Load CSS
try:
    with open('styles.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except Exception as e:
    # Silent error for production
    pass

# Perform an initial data fetch/update when the app starts
if not st.session_state.get('initialized', False):
    update_data_once()
    st.session_state.initialized = True

# Apply background style based on current theme state
st.markdown(get_background_style(), unsafe_allow_html=True)

# Load CSV data for historical display and predictions
initial_df = st.session_state.df if st.session_state.df is not None else load_csv_data()

# Check if we have valid data
if initial_df is not None and not initial_df.empty:
    # ML Prediction
    def predict_weather():
        df = initial_df
        X = np.arange(len(df.index)).reshape(-1, 1)
        temp_model = LinearRegression()
        temp_model.fit(X, df['temperature'])
        next_temp = temp_model.predict([[len(df.index)]])[0]
        humid_model = LinearRegression()
        humid_model.fit(X, df['humidity'])
        next_humid = humid_model.predict([[len(df.index)]])[0]
        return round(next_temp, 1), round(next_humid, 1)

    # Main container
    with st.container():
        col1, col2 = st.columns([4, 1])

        with col1:
            st.markdown(f"<h1 class='location'>{'🌙' if st.session_state.dark_mode else '☀️'} Weather Dashboard</h1>", unsafe_allow_html=True)
            st.markdown(f"<p class='datetime'>{datetime.now().strftime('%B %d, %Y %H:%M')}</p>", unsafe_allow_html=True)
            # Format the last update time to show how long ago the update occurred
            last_update_delta = datetime.now() - st.session_state.last_update_time
            if last_update_delta.total_seconds() < 60:
                last_update_text = f"{int(last_update_delta.total_seconds())} seconds ago"
            elif last_update_delta.total_seconds() < 3600:
                last_update_text = f"{int(last_update_delta.total_seconds() // 60)} minutes ago"
            else:
                last_update_text = f"{st.session_state.last_update_time.strftime('%H:%M:%S')}"
            
            st.markdown(f"<p class='datetime'>Last Update: {last_update_text}</p>", unsafe_allow_html=True)

        with col2:
            # Use a custom toggle button that doesn't cause a page refresh
            if st.button("🌓 Toggle Theme", key="theme_toggle", help="Switch between light and dark mode"):
                toggle_theme()
                # Apply the updated background style without page refresh
                st.markdown(get_background_style(), unsafe_allow_html=True)
                
            # Display current theme indicator
            theme_text = "Dark Mode" if st.session_state.dark_mode else "Light Mode"
            st.markdown(f"<p style='text-align:right; margin-top:-15px; font-size:0.8rem;'>{theme_text}</p>", unsafe_allow_html=True)
            
            # Removed auto-refresh toggle as requested
            
            # Manual refresh button
            if st.button("🔄 Refresh Now", key="manual_refresh"):
                update_data_once()
                st.rerun()  # Only refresh the page when manual refresh is clicked

        # Current weather - Use the live data from session state
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("<div class='weather-card'>", unsafe_allow_html=True)
            st.markdown("<h3>Temperature</h3>", unsafe_allow_html=True)
            st.metric(label="", value=f"{st.session_state.current_temp:.1f}°C", label_visibility="hidden")
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("<div class='weather-card'>", unsafe_allow_html=True)
            st.markdown("<h3>Humidity</h3>", unsafe_allow_html=True)
            st.metric(label="", value=f"{st.session_state.current_humid:.1f}%", label_visibility="hidden")
            st.markdown("</div>", unsafe_allow_html=True)

        with col3:
            st.markdown("<div class='weather-card prediction'>", unsafe_allow_html=True)
            pred_temp, pred_humid = predict_weather()
            st.markdown("### Tomorrow's Prediction")
            st.markdown(f"Temperature: {pred_temp:.1f}°C")
            st.markdown(f"Humidity: {pred_humid:.1f}%")
            st.markdown("</div>", unsafe_allow_html=True)

        # Historical data visualization
        st.markdown("### Historical Data")
        tab1, tab2 = st.tabs(["Temperature", "Humidity"])

        with tab1:
            # Create custom temperature graph with all dates shown on x-axis
            fig_temp = go.Figure()
            
            # Add temperature line
            fig_temp.add_trace(go.Scatter(
                x=initial_df['date'],
                y=initial_df['temperature'],
                mode='lines+markers',
                name='Temperature',
                line=dict(color='royalblue', width=2)
            ))
            
            # Configure axes and layout
            fig_temp.update_layout(
                title='Temperature Trend',
                xaxis=dict(
                    title='Date',
                    tickmode='array',
                    tickvals=initial_df['date'],
                    ticktext=initial_df['date'].dt.strftime('%Y-%m-%d'),
                    tickangle=45,
                    showticklabels=True,
                    showgrid=True
                ),
                yaxis=dict(
                    title='Temperature (°C)',
                    showgrid=True
                ),
                template='plotly_dark' if st.session_state.dark_mode else 'plotly_white',
                height=500,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_temp, use_container_width=True)

        with tab2:
            # Create custom humidity graph with all dates shown on x-axis
            fig_humid = go.Figure()
            
            # Add humidity line
            fig_humid.add_trace(go.Scatter(
                x=initial_df['date'],
                y=initial_df['humidity'],
                mode='lines+markers',
                name='Humidity',
                line=dict(color='seagreen', width=2)
            ))
            
            # Configure axes and layout
            fig_humid.update_layout(
                title='Humidity Trend',
                xaxis=dict(
                    title='Date',
                    tickmode='array',
                    tickvals=initial_df['date'],
                    ticktext=initial_df['date'].dt.strftime('%Y-%m-%d'),
                    tickangle=45,
                    showticklabels=True,
                    showgrid=True
                ),
                yaxis=dict(
                    title='Humidity (%)',
                    showgrid=True
                ),
                template='plotly_dark' if st.session_state.dark_mode else 'plotly_white',
                height=500,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_humid, use_container_width=True)
else:
    st.error("Unable to process weather data. Please check your data sources.")
    # Hide diagnostic information in production
    if st.checkbox("Show diagnostic information", value=False):
        st.write("Diagnostic Information:")
        st.write(f"Current Working Directory: {os.getcwd()}")
        st.write("Contents of current directory:")
        st.write(os.listdir('.'))
        
        # Add network diagnostic button
        if st.button("Test Server Connection"):
            try:
                response = requests.get("http://192.168.23.145:5000/live-data", timeout=5)
                st.write(f"Server Status: {response.status_code}")
                st.write(f"Response Content: {response.text}")
            except Exception as e:
                st.write(f"Server Connection Error: {str(e)}")
