# config.py (shared configuration file)
class Config:
    # Database settings
    DATABASE_CONFIG = {
        'host': 'localhost',
        'database': 'weather_station',
        'user': 'root',
        'password': '2004'
    }
    
    # API settings
    API_BASE_URL = 'http://192.168.170.145:5000/api/v1'
    API_HOST = '0.0.0.0'
    API_PORT = 5000
    
    # File upload settings
    UPLOAD_FOLDER = 'firmware'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Dashboard settings
    DASHBOARD_HOST = '0.0.0.0'
    WEATHER_DASHBOARD_PORT = 8501
    FIRMWARE_DASHBOARD_PORT = 8502