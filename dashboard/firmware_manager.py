import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import os
from config import Config

# Configuration
API_BASE_URL = Config.API_BASE_URL

# Page configuration
st.set_page_config(
    page_title="Firmware Management",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Helper functions
def fetch_data(endpoint: str, params: dict = None):
    """Fetch data from API endpoint"""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching data: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None

def upload_firmware(file, version, description, is_stable):
    """Upload firmware to server"""
    try:
        files = {'file': file}
        data = {
            'version': version,
            'description': description,
            'is_stable': str(is_stable).lower()
        }
        
        response = requests.post(f"{API_BASE_URL}/firmware/upload", files=files, data=data)
        
        if response.status_code == 201:
            return True, "Firmware uploaded successfully"
        else:
            return False, f"Error: {response.json().get('message', 'Unknown error')}"
    except Exception as e:
        return False, f"Error uploading firmware: {str(e)}"

def show_firmware_versions():
    """Display firmware versions"""
    st.header("Firmware Versions")
    
    # Fetch firmware versions
    versions_data = fetch_data("/firmware/list")
    
    if versions_data and versions_data['status'] == 'success':
        versions = versions_data['versions']
        
        if versions:
            # Create DataFrame
            df = pd.DataFrame(versions)
            df['release_date'] = pd.to_datetime(df['release_date']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Display versions in a table
            st.dataframe(
                df[['version', 'description', 'release_date', 'is_stable', 'checksum']],
                use_container_width=True
            )
            
            # Detailed view of selected version
            selected_version = st.selectbox(
                "Select version for details",
                options=[v['version'] for v in versions],
                format_func=lambda x: f"v{x}"
            )
            
            if selected_version:
                version_details = next(v for v in versions if v['version'] == selected_version)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Version Details")
                    st.write(f"**Version:** {version_details['version']}")
                    st.write(f"**Release Date:** {version_details['release_date']}")
                    st.write(f"**Stable:** {'Yes' if version_details['is_stable'] else 'No'}")
                    st.write(f"**Filename:** {version_details['filename']}")
                
                with col2:
                    st.subheader("Technical Details")
                    st.write(f"**Checksum:** `{version_details['checksum']}`")
                    if version_details.get('min_hardware_version'):
                        st.write(f"**Min Hardware Version:** {version_details['min_hardware_version']}")
                    
                    if st.button("Download Firmware"):
                        download_url = f"{API_BASE_URL}/firmware/download/{selected_version}"
                        st.markdown(f"[Download Firmware v{selected_version}]({download_url})")
                
                if version_details['description']:
                    st.subheader("Description")
                    st.write(version_details['description'])
        else:
            st.info("No firmware versions available")
    else:
        st.error("Failed to fetch firmware versions")

def show_device_management():
    """Display device management interface"""
    st.header("Device Management")
    
    # Fetch devices
    devices_data = fetch_data("/devices")
    
    if devices_data and devices_data['status'] == 'success':
        devices = devices_data['devices']
        
        if devices:
            # Create DataFrame
            df = pd.DataFrame(devices)
            # Convert datetime columns safely
            if 'last_seen' in df.columns and df['last_seen'].notna().any():
                df['last_seen'] = pd.to_datetime(df['last_seen']).dt.strftime('%Y-%m-%d %H:%M')
            if 'registered_at' in df.columns:
                df['registered_at'] = pd.to_datetime(df['registered_at']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Display devices in a table
            display_columns = ['device_id', 'current_firmware', 'last_seen', 'last_ip', 'auto_update']
            available_columns = [col for col in display_columns if col in df.columns]
            st.dataframe(
                df[available_columns],
                use_container_width=True
            )
            
            # Device details and management
            selected_device = st.selectbox(
                "Select device for management",
                options=[d['device_id'] for d in devices]
            )
            
            if selected_device:
                device_details = next(d for d in devices if d['device_id'] == selected_device)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Device Information")
                    st.write(f"**Device ID:** {device_details['device_id']}")
                    st.write(f"**Current Firmware:** {device_details.get('current_firmware', 'Unknown')}")
                    st.write(f"**Last Seen:** {device_details.get('last_seen', 'Never')}")
                    st.write(f"**Last IP:** {device_details.get('last_ip', 'Unknown')}")
                
                with col2:
                    st.subheader("Device Settings")
                    
                    # Auto-update toggle
                    auto_update = st.checkbox(
                        "Auto-update enabled",
                        value=device_details.get('auto_update', False),
                        key=f"auto_update_{selected_device}"
                    )
                    
                    if auto_update != device_details.get('auto_update', False):
                        if st.button("Save Settings"):
                            try:
                                response = requests.post(
                                    f"{API_BASE_URL}/devices/{selected_device}/config",
                                    json={"auto_update": auto_update}
                                )
                                if response.status_code == 200:
                                    st.success("Settings updated successfully")
                                    st.rerun()
                                else:
                                    st.error("Failed to update settings")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                
                # Firmware update section
                st.subheader("Firmware Update")
                
                # Check for updates
                if st.button("Check for Updates"):
                    try:
                        response = requests.get(
                            f"{API_BASE_URL}/firmware/check",
                            params={
                                "device_id": selected_device,
                                "current_version": device_details.get('current_firmware', '0.0.0')
                            }
                        )
                        
                        if response.status_code == 200:
                            update_info = response.json()
                            
                            if update_info.get('update_available', False):
                                st.info(f"Update available: v{update_info['new_version']}")
                                st.write(f"**Description:** {update_info.get('description', 'No description available')}")
                                st.write(f"**Release Date:** {update_info.get('release_date', 'Unknown')}")
                                
                                if st.button("Install Update"):
                                    st.info("Update notification sent to device. The device will update automatically when ready.")
                            else:
                                st.success("Device is running the latest firmware")
                        else:
                            st.error("Failed to check for updates")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        else:
            st.info("No devices registered")
    else:
        st.error("Failed to fetch devices")

def show_upload_firmware():
    """Display firmware upload interface"""
    st.header("Upload New Firmware")
    
    with st.form("firmware_upload_form"):
        st.subheader("Firmware Details")
        
        # Firmware file upload
        firmware_file = st.file_uploader(
            "Select firmware file (.bin)",
            type=['bin'],
            help="Upload the compiled firmware binary file"
        )
        
        # Version input
        version = st.text_input(
            "Version",
            placeholder="e.g., 1.2.0",
            help="Semantic version number for this firmware"
        )
        
        # Description
        description = st.text_area(
            "Description",
            placeholder="Describe the changes in this version",
            help="Changelog and release notes"
        )
        
        # Stability flag
        is_stable = st.checkbox(
            "Mark as stable release",
            value=True,
            help="Stable releases are offered to devices with auto-update enabled"
        )
        
        # Submit button
        submitted = st.form_submit_button("Upload Firmware")
        
        if submitted:
            if not firmware_file:
                st.error("Please select a firmware file")
            elif not version:
                st.error("Please enter a version number")
            else:
                with st.spinner("Uploading firmware..."):
                    success, message = upload_firmware(
                        firmware_file,
                        version,
                        description,
                        is_stable
                    )
                    
                    if success:
                        st.success(message)
                        st.balloons()
                    else:
                        st.error(message)
    
    # Recent uploads
    st.subheader("Recent Firmware Uploads")
    
    versions_data = fetch_data("/firmware/list")
    
    if versions_data and versions_data['status'] == 'success':
        versions = versions_data['versions'][:5]  # Show only the 5 most recent
        
        if versions:
            for version in versions:
                with st.expander(f"v{version['version']} - {version['release_date']}"):
                    st.write(f"**Description:** {version.get('description', 'No description')}")
                    st.write(f"**Stable:** {'Yes' if version.get('is_stable', False) else 'No'}")
                    st.write(f"**Checksum:** `{version.get('checksum', 'N/A')}`")

def show_dashboard():
    """Display dashboard overview"""
    st.header("Dashboard Overview")
    
    # Fetch summary data
    devices_data = fetch_data("/devices")
    versions_data = fetch_data("/firmware/list")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Devices",
            len(devices_data['devices']) if devices_data and 'devices' in devices_data else 0
        )
    
    with col2:
        st.metric(
            "Firmware Versions",
            len(versions_data['versions']) if versions_data and 'versions' in versions_data else 0
        )
    
    with col3:
        if devices_data and 'devices' in devices_data and devices_data['devices']:
            online_devices = sum(1 for d in devices_data['devices'] 
                               if d.get('last_seen') and 
                               (datetime.now() - datetime.fromisoformat(d['last_seen'])).total_seconds() < 600)
            st.metric("Online Devices", online_devices)
        else:
            st.metric("Online Devices", 0)
    
    # Recent activity
    st.subheader("Recent Activity")
    
    if devices_data and 'devices' in devices_data and devices_data['devices']:
        recent_devices = sorted(
            devices_data['devices'],
            key=lambda x: x.get('last_seen', ''),
            reverse=True
        )[:5]
        
        for device in recent_devices:
            if device.get('last_seen'):
                try:
                    last_seen = datetime.fromisoformat(device['last_seen'])
                    time_ago = datetime.now() - last_seen
                    
                    if time_ago.total_seconds() < 60:
                        time_str = "just now"
                    elif time_ago.total_seconds() < 3600:
                        time_str = f"{int(time_ago.total_seconds() // 60)} minutes ago"
                    elif time_ago.total_seconds() < 86400:
                        time_str = f"{int(time_ago.total_seconds() // 3600)} hours ago"
                    else:
                        time_str = f"{int(time_ago.total_seconds() // 86400)} days ago"
                    
                    st.write(f"**{device['device_id']}** - Last seen {time_str} (Firmware: {device.get('current_firmware', 'Unknown')})")
                except Exception as e:
                    st.write(f"**{device['device_id']}** - Last seen: Unknown (Firmware: {device.get('current_firmware', 'Unknown')})")
    else:
        st.info("No device activity to display")

def main():
    st.title("🔧 Firmware Management Dashboard")
    
    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Navigation",
        ["Dashboard", "Firmware Versions", "Device Management", "Upload Firmware"]
    )
    
    if page == "Dashboard":
        show_dashboard()
    elif page == "Firmware Versions":
        show_firmware_versions()
    elif page == "Device Management":
        show_device_management()
    elif page == "Upload Firmware":
        show_upload_firmware()

if __name__ == "__main__":
    main()