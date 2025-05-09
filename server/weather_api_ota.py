# weather_api_ota.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import logging
import hashlib
from werkzeug.utils import secure_filename
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Database configuration
db_config = Config.DATABASE_CONFIG
db_url = f"mysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

# Ensure firmware directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Database models (same as before)
class SensorData(db.Model):
    __tablename__ = 'sensor_data'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    firmware_version = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'firmware_version': self.firmware_version,
            'timestamp': self.timestamp.isoformat(),
            'created_at': self.created_at.isoformat()
        }

class FirmwareVersion(db.Model):
    __tablename__ = 'firmware_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(20), nullable=False, unique=True)
    filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    release_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_stable = db.Column(db.Boolean, default=True)
    min_hardware_version = db.Column(db.String(20))
    checksum = db.Column(db.String(64))

    def to_dict(self):
        return {
            'id': self.id,
            'version': self.version,
            'filename': self.filename,
            'description': self.description,
            'release_date': self.release_date.isoformat(),
            'is_stable': self.is_stable,
            'min_hardware_version': self.min_hardware_version,
            'checksum': self.checksum
        }

class DeviceRegistry(db.Model):
    __tablename__ = 'device_registry'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, unique=True)
    hardware_version = db.Column(db.String(20))
    current_firmware = db.Column(db.String(20))
    last_seen = db.Column(db.DateTime)
    last_ip = db.Column(db.String(45))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    auto_update = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'hardware_version': self.hardware_version,
            'current_firmware': self.current_firmware,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'last_ip': self.last_ip,
            'registered_at': self.registered_at.isoformat(),
            'auto_update': self.auto_update
        }

# Create database tables
with app.app_context():
    db.create_all()
    
# Helper functions
def calculate_file_hash(filepath):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def version_compare(v1, v2):
    """Compare two version strings (e.g., "1.0.0" vs "1.1.0")"""
    v1_parts = [int(x) for x in v1.split('.')]
    v2_parts = [int(x) for x in v2.split('.')]
    
    for i in range(max(len(v1_parts), len(v2_parts))):
        v1_part = v1_parts[i] if i < len(v1_parts) else 0
        v2_part = v2_parts[i] if i < len(v2_parts) else 0
        
        if v1_part > v2_part:
            return 1
        elif v1_part < v2_part:
            return -1
    
    return 0

# API Routes
@app.route('/api/v1/sensor/data', methods=['POST'])
def receive_sensor_data():
    """Endpoint to receive sensor data from ESP32"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['device_id', 'temperature', 'humidity']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Validate data types and ranges
        try:
            temperature = float(data['temperature'])
            humidity = float(data['humidity'])
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid data type for temperature or humidity'
            }), 400
        
        # Validate reasonable ranges
        if not (-50 <= temperature <= 100):
            return jsonify({
                'status': 'error',
                'message': 'Temperature out of reasonable range'
            }), 400
        
        if not (0 <= humidity <= 100):
            return jsonify({
                'status': 'error',
                'message': 'Humidity out of reasonable range'
            }), 400
        
        # Parse timestamp if provided
        timestamp = datetime.utcnow()
        if 'timestamp' in data:
            try:
                timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Invalid timestamp format: {data['timestamp']}")
        
        # Get firmware version if provided
        firmware_version = data.get('firmware_version', 'unknown')
        
        # Create new sensor data record
        sensor_data = SensorData(
            device_id=data['device_id'],
            temperature=temperature,
            humidity=humidity,
            firmware_version=firmware_version,
            timestamp=timestamp
        )
        
        db.session.add(sensor_data)
        
        # Update device registry
        device = DeviceRegistry.query.filter_by(device_id=data['device_id']).first()
        if device:
            device.last_seen = datetime.utcnow()
            device.last_ip = request.remote_addr
            device.current_firmware = firmware_version
        else:
            # Register new device
            device = DeviceRegistry(
                device_id=data['device_id'],
                current_firmware=firmware_version,
                last_seen=datetime.utcnow(),
                last_ip=request.remote_addr
            )
            db.session.add(device)
        
        db.session.commit()
        
        logger.info(f"Received data from {data['device_id']}: {temperature}°C, {humidity}%")
        
        return jsonify({
            'status': 'success',
            'message': 'Data received successfully',
            'data': sensor_data.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error processing sensor data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

# Firmware management routes
@app.route('/api/v1/firmware/check', methods=['GET'])
def check_firmware_update():
    """Check if firmware update is available for a device"""
    device_id = request.args.get('device_id')
    current_version = request.args.get('current_version')
    
    if not device_id or not current_version:
        return jsonify({
            'status': 'error',
            'message': 'Missing device_id or current_version'
        }), 400
    
    # Get the latest stable firmware
    latest_firmware = FirmwareVersion.query.filter_by(is_stable=True).order_by(FirmwareVersion.release_date.desc()).first()
    
    if not latest_firmware:
        return jsonify({
            'status': 'success',
            'update_available': False,
            'message': 'No firmware available'
        })
    
    # Check if update is available
    update_available = version_compare(latest_firmware.version, current_version) > 0
    
    response = {
        'status': 'success',
        'update_available': update_available,
        'current_version': current_version,
        'latest_version': latest_firmware.version
    }
    
    if update_available:
        response.update({
            'new_version': latest_firmware.version,
            'description': latest_firmware.description,
            'release_date': latest_firmware.release_date.isoformat(),
            'firmware_url': f"{request.host_url}api/v1/firmware/download/{latest_firmware.version}",
            'checksum': latest_firmware.checksum
        })
    
    return jsonify(response)

@app.route('/api/v1/firmware/upload', methods=['POST'])
def upload_firmware():
    """Upload new firmware version"""
    # Check if file is present
    if 'file' not in request.files:
        return jsonify({
            'status': 'error',
            'message': 'No file provided'
        }), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            'status': 'error',
            'message': 'No file selected'
        }), 400
    
    # Get version and description from form data
    version = request.form.get('version')
    description = request.form.get('description', '')
    is_stable = request.form.get('is_stable', 'true').lower() == 'true'
    
    if not version:
        return jsonify({
            'status': 'error',
            'message': 'Version is required'
        }), 400
    
    # Check if version already exists
    existing = FirmwareVersion.query.filter_by(version=version).first()
    if existing:
        return jsonify({
            'status': 'error',
            'message': 'Version already exists'
        }), 400
    
    # Save file
    filename = secure_filename(f"firmware_v{version}.bin")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Calculate checksum
    checksum = calculate_file_hash(filepath)
    
    # Create database entry
    firmware = FirmwareVersion(
        version=version,
        filename=filename,
        description=description,
        is_stable=is_stable,
        checksum=checksum
    )
    
    db.session.add(firmware)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Firmware uploaded successfully',
        'firmware': firmware.to_dict()
    }), 201

@app.route('/api/v1/firmware/download/<version>', methods=['GET'])
def download_firmware(version):
    """Download firmware file"""
    firmware = FirmwareVersion.query.filter_by(version=version).first()
    
    if not firmware:
        return jsonify({
            'status': 'error',
            'message': 'Firmware version not found'
        }), 404
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], firmware.filename)
    
    if not os.path.exists(filepath):
        return jsonify({
            'status': 'error',
            'message': 'Firmware file not found'
        }), 404
    
    return send_file(filepath, as_attachment=True, download_name=firmware.filename)

@app.route('/api/v1/firmware/list', methods=['GET'])
def list_firmware_versions():
    """List all firmware versions"""
    versions = FirmwareVersion.query.order_by(FirmwareVersion.release_date.desc()).all()
    
    return jsonify({
        'status': 'success',
        'count': len(versions),
        'versions': [v.to_dict() for v in versions]
    })

@app.route('/api/v1/devices', methods=['GET'])
def list_devices():
    """List all registered devices"""
    devices = DeviceRegistry.query.all()
    
    return jsonify({
        'status': 'success',
        'count': len(devices),
        'devices': [d.to_dict() for d in devices]
    })

@app.route('/api/v1/devices/<device_id>/config', methods=['GET', 'POST'])
def device_config(device_id):
    """Get or update device configuration"""
    device = DeviceRegistry.query.filter_by(device_id=device_id).first()
    
    if not device:
        return jsonify({
            'status': 'error',
            'message': 'Device not found'
        }), 404
    
    if request.method == 'GET':
        return jsonify({
            'status': 'success',
            'device': device.to_dict()
        })
    
    # POST - update device configuration
    data = request.get_json()
    
    if 'auto_update' in data:
        device.auto_update = data['auto_update']
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Device configuration updated',
        'device': device.to_dict()
    })

@app.route('/api/v1/sensor/latest', methods=['GET'])
def get_latest_data():
    """Get the latest sensor reading"""
    try:
        device_id = request.args.get('device_id')
        
        query = SensorData.query.order_by(SensorData.timestamp.desc())
        
        if device_id:
            query = query.filter_by(device_id=device_id)
        
        latest_data = query.first()
        
        if not latest_data:
            return jsonify({
                'status': 'error',
                'message': 'No data available'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': latest_data.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error fetching latest data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/api/v1/sensor/history', methods=['GET'])
def get_historical_data():
    """Get historical sensor data"""
    try:
        device_id = request.args.get('device_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 100, type=int)
        
        query = SensorData.query.order_by(SensorData.timestamp.desc())
        
        if device_id:
            query = query.filter_by(device_id=device_id)
        
        if start_date:
            try:
                start = datetime.fromisoformat(start_date)
                query = query.filter(SensorData.timestamp >= start)
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid start_date format'
                }), 400
        
        if end_date:
            try:
                end = datetime.fromisoformat(end_date)
                query = query.filter(SensorData.timestamp <= end)
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid end_date format'
                }), 400
        
        data = query.limit(limit).all()
        
        return jsonify({
            'status': 'success',
            'count': len(data),
            'data': [item.to_dict() for item in data]
        })
        
    except Exception as e:
        logger.error(f"Error fetching historical data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500
        
@app.route('/api/v1/sensor/stats', methods=['GET'])
def get_sensor_stats():
    """Get statistical data about sensor readings"""
    try:
        device_id = request.args.get('device_id')
        period = request.args.get('period', '24h')
        
        if not device_id:
            return jsonify({
                'status': 'error',
                'message': 'Missing device_id parameter'
            }), 400
        
        # Parse period to determine time range
        time_ranges = {
            '1h': timedelta(hours=1),
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30)
        }
        
        time_range = time_ranges.get(period, timedelta(hours=24))
        start_time = datetime.utcnow() - time_range
        
        # Query sensor data within the time range
        data = SensorData.query.filter(
            SensorData.device_id == device_id,
            SensorData.timestamp >= start_time
        ).all()
        
        if not data:
            return jsonify({
                'status': 'success',
                'stats': {
                    'temperature': {'min': 0, 'max': 0, 'avg': 0},
                    'humidity': {'min': 0, 'max': 0, 'avg': 0},
                    'data_points': 0
                }
            })
        
        # Calculate statistics
        temperatures = [d.temperature for d in data]
        humidities = [d.humidity for d in data]
        
        stats = {
            'temperature': {
                'min': min(temperatures),
                'max': max(temperatures),
                'avg': sum(temperatures) / len(temperatures)
            },
            'humidity': {
                'min': min(humidities),
                'max': max(humidities),
                'avg': sum(humidities) / len(humidities)
            },
            'data_points': len(data)
        }
        
        return jsonify({
            'status': 'success',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error calculating stats: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Error calculating statistics'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)