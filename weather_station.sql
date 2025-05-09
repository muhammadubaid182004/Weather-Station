USE weather_station;

-- 1. Sensor Data Table
-- This table stores all temperature and humidity readings from the ESP32 devices
CREATE TABLE IF NOT EXISTS sensor_data (
    id INT AUTO_INCREMENT PRIMARY KEY,           -- Unique identifier for each reading
    device_id VARCHAR(50) NOT NULL,              -- Identifier of the ESP32 device (e.g., "ESP32_001")
    temperature FLOAT NOT NULL,                  -- Temperature reading in Celsius
    humidity FLOAT NOT NULL,                     -- Humidity reading in percentage
    firmware_version VARCHAR(20),                -- Current firmware version of the device
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, -- When the reading was taken
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- When the record was created in database
    INDEX idx_device_id (device_id),             -- Index for faster device-specific queries
    INDEX idx_timestamp (timestamp)              -- Index for faster time-based queries
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Firmware Versions Table
-- This table stores information about all firmware versions available for devices
CREATE TABLE IF NOT EXISTS firmware_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,           -- Unique identifier for each firmware
    version VARCHAR(20) NOT NULL UNIQUE,         -- Version number (e.g., "1.0.0", "1.1.0")
    filename VARCHAR(255) NOT NULL,              -- Name of the firmware file
    description TEXT,                            -- Release notes/changelog for this version
    release_date DATETIME DEFAULT CURRENT_TIMESTAMP, -- When this version was released
    is_stable BOOLEAN DEFAULT TRUE,              -- Whether this is a stable release
    min_hardware_version VARCHAR(20),            -- Minimum hardware version required
    checksum VARCHAR(64),                        -- SHA256 hash of the firmware file
    file_size INT,                               -- Size of firmware file in bytes
    INDEX idx_version (version),                 -- Index for faster version lookups
    INDEX idx_release_date (release_date)        -- Index for sorting by release date
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Device Registry Table
-- This table keeps track of all ESP32 devices and their current status
CREATE TABLE IF NOT EXISTS device_registry (
    id INT AUTO_INCREMENT PRIMARY KEY,           -- Unique identifier for each device
    device_id VARCHAR(50) NOT NULL UNIQUE,       -- Device identifier (must be unique)
    hardware_version VARCHAR(20),                -- Hardware version of the device
    current_firmware VARCHAR(20),                -- Current firmware version installed
    last_seen DATETIME,                          -- Last time device contacted server
    last_ip VARCHAR(45),                         -- Last known IP address (supports IPv6)
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- When device was first registered
    auto_update BOOLEAN DEFAULT TRUE,            -- Whether device should auto-update
    location VARCHAR(100),                       -- Optional: physical location of device
    notes TEXT,                                  -- Optional: admin notes about device
    INDEX idx_device_id (device_id),             -- Index for faster device lookups
    INDEX idx_last_seen (last_seen)              -- Index for finding inactive devices
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Update History Table (Optional but recommended)
-- This table tracks all firmware updates performed on devices
CREATE TABLE IF NOT EXISTS update_history (
    id INT AUTO_INCREMENT PRIMARY KEY,           -- Unique identifier for each update
    device_id VARCHAR(50) NOT NULL,              -- Device that was updated
    from_version VARCHAR(20),                    -- Previous firmware version
    to_version VARCHAR(20) NOT NULL,             -- New firmware version
    update_started DATETIME NOT NULL,            -- When update began
    update_completed DATETIME,                   -- When update finished (NULL if failed)
    status ENUM('started', 'downloading', 'installing', 'completed', 'failed') DEFAULT 'started',
    error_message TEXT,                          -- Error details if update failed
    INDEX idx_device_id (device_id),             -- Index for device update history
    INDEX idx_status (status),                   -- Index for finding failed updates
    FOREIGN KEY (device_id) REFERENCES device_registry(device_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Daily Statistics Table (Optional but useful for dashboards)
-- This table stores pre-calculated daily statistics for faster dashboard loading
CREATE TABLE IF NOT EXISTS daily_statistics (
    id INT AUTO_INCREMENT PRIMARY KEY,           -- Unique identifier
    device_id VARCHAR(50) NOT NULL,              -- Device these stats are for
    date DATE NOT NULL,                          -- Date of statistics
    avg_temperature FLOAT,                       -- Average temperature for the day
    min_temperature FLOAT,                       -- Minimum temperature
    max_temperature FLOAT,                       -- Maximum temperature
    avg_humidity FLOAT,                          -- Average humidity
    min_humidity FLOAT,                          -- Minimum humidity
    max_humidity FLOAT,                          -- Maximum humidity
    reading_count INT DEFAULT 0,                 -- Number of readings for the day
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- When stats were calculated
    UNIQUE KEY unique_device_date (device_id, date), -- Ensure one entry per device per day
    INDEX idx_date (date)                        -- Index for date-based queries
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Create a view for the latest readings per device
CREATE OR REPLACE VIEW latest_readings AS
SELECT 
    d.device_id,
    d.current_firmware,
    d.last_seen,
    d.last_ip,
    s.temperature,
    s.humidity,
    s.timestamp as reading_time
FROM device_registry d
LEFT JOIN (
    SELECT 
        device_id,
        temperature,
        humidity,
        timestamp,
        ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY timestamp DESC) as rn
    FROM sensor_data
) s ON d.device_id = s.device_id AND s.rn = 1;

-- Create a stored procedure to calculate daily statistics
DELIMITER //

CREATE PROCEDURE calculate_daily_stats(IN calc_date DATE)
BEGIN
    -- Delete existing stats for the date to avoid duplicates
    DELETE FROM daily_statistics WHERE date = calc_date;
    
    -- Insert new statistics
    INSERT INTO daily_statistics (
        device_id, date, 
        avg_temperature, min_temperature, max_temperature,
        avg_humidity, min_humidity, max_humidity,
        reading_count
    )
    SELECT 
        device_id,
        DATE(timestamp) as date,
        AVG(temperature) as avg_temperature,
        MIN(temperature) as min_temperature,
        MAX(temperature) as max_temperature,
        AVG(humidity) as avg_humidity,
        MIN(humidity) as min_humidity,
        MAX(humidity) as max_humidity,
        COUNT(*) as reading_count
    FROM sensor_data
    WHERE DATE(timestamp) = calc_date
    GROUP BY device_id, DATE(timestamp);
END //

DELIMITER ;

-- Create triggers to maintain data integrity
DELIMITER //

-- Trigger to update device registry when new sensor data arrives
CREATE TRIGGER update_device_on_sensor_data
AFTER INSERT ON sensor_data
FOR EACH ROW
BEGIN
    UPDATE device_registry
    SET 
        last_seen = NEW.timestamp,
        current_firmware = COALESCE(NEW.firmware_version, current_firmware)
    WHERE device_id = NEW.device_id;
    
    -- If device doesn't exist, create it
    INSERT IGNORE INTO device_registry (device_id, current_firmware, last_seen)
    VALUES (NEW.device_id, NEW.firmware_version, NEW.timestamp);
END //

DELIMITER ;

-- Sample data for testing
-- Insert a test device
INSERT INTO device_registry (device_id, hardware_version, current_firmware, auto_update)
VALUES ('ESP32_001', '1.0', '1.0.0', TRUE);

-- Insert a test firmware version
INSERT INTO firmware_versions (version, filename, description, is_stable)
VALUES ('1.0.0', 'firmware_v1.0.0.bin', 'Initial release', TRUE);

-- Insert some test sensor data
INSERT INTO sensor_data (device_id, temperature, humidity, firmware_version)
VALUES 
    ('ESP32_001', 25.5, 60.2, '1.0.0'),
    ('ESP32_001', 25.7, 59.8, '1.0.0'),
    ('ESP32_001', 25.6, 60.0, '1.0.0');

-- Useful queries for monitoring and maintenance

-- Get all devices that haven't been seen in the last hour
SELECT device_id, last_seen, current_firmware
FROM device_registry
WHERE last_seen < DATE_SUB(NOW(), INTERVAL 1 HOUR);

-- Get average readings for the last 24 hours per device
SELECT 
    device_id,
    AVG(temperature) as avg_temp,
    AVG(humidity) as avg_humidity,
    COUNT(*) as reading_count
FROM sensor_data
WHERE timestamp > DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY device_id;

-- Find devices that need firmware updates
SELECT 
    dr.device_id,
    dr.current_firmware,
    fv.version as latest_version
FROM device_registry dr
CROSS JOIN (
    SELECT version 
    FROM firmware_versions 
    WHERE is_stable = TRUE 
    ORDER BY release_date DESC 
    LIMIT 1
) fv
WHERE dr.current_firmware != fv.version AND dr.auto_update = TRUE;

-- Clean up old sensor data (keep last 90 days)
DELETE FROM sensor_data 
WHERE timestamp < DATE_SUB(NOW(), INTERVAL 90 DAY);

-- Calculate yesterday's statistics
CALL calculate_daily_stats(DATE_SUB(CURDATE(), INTERVAL 1 DAY));

-- Find devices that haven't reported in 24 hours
SELECT device_id, last_seen 
FROM device_registry 
WHERE last_seen < DATE_SUB(NOW(), INTERVAL 24 HOUR);