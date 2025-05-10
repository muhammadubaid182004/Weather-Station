#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <time.h>
#include <EEPROM.h>
#include <Update.h>
#include <ArduinoOTA.h>

// Configuration
#define DHTPIN 4
#define DHTTYPE DHT11
#define WIFI_RETRY_DELAY 500
#define MAX_WIFI_RETRIES 20
#define SENSOR_READ_INTERVAL 30000  // 30 seconds
#define SERVER_TIMEOUT 10000
#define EEPROM_SIZE 512
#define FIRMWARE_VERSION "1.0.2"

// WiFi credentials
const char* ssid = "Infinix HOT 40 Pro";
const char* password = "18feburary2004";

// Server configuration - Make sure this is correct!
// Update these lines in your code
// Idhar ipconfig k output wale ip likho ge(matlab aap k computer k ip or yahi server URL online wali configuration mai daalo)
const char* serverUrl = "http://192.168.170.145:5000/api/v1/sensor/data";
const char* updateCheckUrl = "http://192.168.170.145:5000/api/v1/firmware/check";
const char* deviceId = "ESP32_001";

// OTA credentials
const char* otaUsername = "admin";
const char* otaPassword = "admin123";

DHT dht(DHTPIN, DHTTYPE);
WebServer server(80);

// Global variables
unsigned long lastReadTime = 0;
unsigned long lastUpdateCheck = 0;
bool wifiConnected = false;
String currentFirmwareVersion = FIRMWARE_VERSION;

// Structure to store persistent configuration
struct Config {
  char ssid[32];
  char password[64];
  char serverUrl[128];
  char deviceId[32];
  uint32_t checksum;
};

Config config;

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    ; // Wait for serial port to connect
  }
  
  // Clear any garbage in serial buffer
  while (Serial.available()) {
    Serial.read();
  }
  
  Serial.println("\n\nWeather Station Starting...");
  Serial.print("Firmware Version: ");
  Serial.println(currentFirmwareVersion);
  
  // Initialize EEPROM
  EEPROM.begin(EEPROM_SIZE);
  loadConfig();
  
  // Initialize sensor
  dht.begin();
  
  // Connect to WiFi
  connectToWiFi();
  
  // Configure time
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  
  // Setup web server
  setupWebServer();

  ArduinoOTA.setHostname("ESP32-OTA");
    ArduinoOTA.setPassword(otaPassword);
    
    // Set the OTA event handlers
    ArduinoOTA.onStart(onOTAStart);
    ArduinoOTA.onEnd([]() {
        Serial.println("OTA End");
    });
    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
        Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
    });
    ArduinoOTA.onError([](ota_error_t error) {
        Serial.printf("Error: ");
        if (error == OTA_AUTH_ERROR) {
            Serial.println("Auth Failed");
        } else if (error == OTA_BEGIN_ERROR) {
            Serial.println("Begin Failed");
        } else if (error == OTA_CONNECT_ERROR) {
            Serial.println("Connect Failed");
        } else if (error == OTA_RECEIVE_ERROR) {
            Serial.println("Receive Failed");
        } else if (error == OTA_END_ERROR) {
            Serial.println("End Failed");
        }
    });

    ArduinoOTA.begin();
}

void loop() {

   
  // Handle web server
  server.handleClient();

  ArduinoOTA.handle();

  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    wifiConnected = false;
    connectToWiFi();
  }
  
  // Read and send sensor data
  if (millis() - lastReadTime >= SENSOR_READ_INTERVAL) {
    readAndSendSensorData();
    lastReadTime = millis();
  }
  
  // Check for firmware updates every hour
  if (millis() - lastUpdateCheck >= 3600000) {
    checkForUpdates();
    lastUpdateCheck = millis();
  }
  
  delay(10);
}

void onOTAStart() {
    String type;
    if (Update.isRunning()) {
        type = "Sketch";
    } else {
        type = "SPIFFS";
    }
    Serial.println("Start updating " + type);
}

void setupWebServer() {
  // Root page
  server.on("/", HTTP_GET, []() {
    String html = "<!DOCTYPE html><html><head>";
    html += "<title>Weather Station</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>body{font-family:Arial,sans-serif;margin:20px;}";
    html += ".container{max-width:600px;margin:0 auto;}";
    html += ".info{background:#f0f0f0;padding:10px;margin:10px 0;border-radius:5px;}";
    html += ".button{display:inline-block;background:#0066cc;color:white;padding:10px 20px;";
    html += "text-decoration:none;border-radius:5px;margin:5px;}";
    html += "</style></head><body><div class='container'>";
    html += "<h1>Weather Station OTA</h1>";
    html += "<div class='info'><p><strong>Device ID:</strong> " + String(config.deviceId) + "</p>";
    html += "<p><strong>Firmware Version:</strong> " + currentFirmwareVersion + "</p>";
    html += "<p><strong>IP Address:</strong> " + WiFi.localIP().toString() + "</p>";
    html += "<p><strong>Free Heap:</strong> " + String(ESP.getFreeHeap()) + " bytes</p></div>";
    html += "<a href='/update' class='button'>Firmware Update</a>";
    html += "<a href='/config' class='button'>Configuration</a>";
    html += "<a href='/check-update' class='button'>Check for Updates</a>";
    html += "</div></body></html>";
    server.send(200, "text/html", html);
  });
  
  // Firmware update page
  server.on("/update", HTTP_GET, []() {
    String html = "<!DOCTYPE html><html><head>";
    html += "<title>Firmware Update</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>body{font-family:Arial,sans-serif;margin:20px;}";
    html += ".container{max-width:600px;margin:0 auto;}";
    html += "</style></head><body><div class='container'>";
    html += "<h1>Firmware Update</h1>";
    html += "<form method='POST' action='/update' enctype='multipart/form-data'>";
    html += "<input type='file' name='update' accept='.bin'><br><br>";
    html += "<input type='submit' value='Update Firmware'>";
    html += "</form>";
    html += "<br><a href='/'>Back to Home</a>";
    html += "</div></body></html>";
    server.send(200, "text/html", html);
  });
  
  // Handle firmware upload
  server.on("/update", HTTP_POST, []() {
    server.sendHeader("Connection", "close");
    String message = Update.hasError() ? "Update Failed!" : "Update Success! Rebooting...";
    server.send(200, "text/plain", message);
    delay(1000);
    ESP.restart();
  }, handleFirmwareUpload);
  
  // Configuration page
  server.on("/config", HTTP_GET, []() {
    String html = "<!DOCTYPE html><html><head>";
    html += "<title>Configuration</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>body{font-family:Arial,sans-serif;margin:20px;}";
    html += ".container{max-width:600px;margin:0 auto;}";
    html += "input[type='text'],input[type='password']{width:100%;padding:8px;margin:5px 0;}";
    html += "</style></head><body><div class='container'>";
    html += "<h1>Device Configuration</h1>";
    html += "<form action='/config' method='POST'>";
    html += "<label>SSID:</label><input type='text' name='ssid' value='" + String(config.ssid) + "'><br>";
    html += "<label>Password:</label><input type='password' name='password'><br>";
    html += "<label>Server URL:</label><input type='text' name='serverUrl' value='" + String(config.serverUrl) + "'><br>";
    html += "<label>Device ID:</label><input type='text' name='deviceId' value='" + String(config.deviceId) + "'><br><br>";
    html += "<input type='submit' value='Save Configuration'>";
    html += "</form>";
    html += "<br><a href='/'>Back to Home</a>";
    html += "</div></body></html>";
    server.send(200, "text/html", html);
  });
  
  // Handle configuration POST
  server.on("/config", HTTP_POST, []() {
    if (server.hasArg("ssid")) {
      String newSsid = server.arg("ssid");
      String newPassword = server.arg("password");
      String newServerUrl = server.arg("serverUrl");
      String newDeviceId = server.arg("deviceId");
      
      strcpy(config.ssid, newSsid.c_str());
      if (newPassword.length() > 0) {
        strcpy(config.password, newPassword.c_str());
      }
      strcpy(config.serverUrl, newServerUrl.c_str());
      strcpy(config.deviceId, newDeviceId.c_str());
      
      saveConfig();
      server.send(200, "text/html", "Configuration saved! Rebooting...<br><a href='/'>Home</a>");
      delay(2000);
      ESP.restart();
    } else {
      server.send(400, "text/plain", "Missing parameters");
    }
  });
  
  // Manual update check
  server.on("/check-update", HTTP_GET, []() {
    server.send(200, "text/html", "Checking for updates...<br><a href='/'>Home</a>");
    checkForUpdates();
  });
  
  server.begin();
  Serial.println("HTTP server started");
}

void handleFirmwareUpload() {
    HTTPUpload& upload = server.upload();

    if (upload.status == UPLOAD_FILE_START) {
        Serial.printf("Update: %s\n", upload.filename.c_str());
        if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
            Update.printError(Serial);
        }
    } 
    else if (upload.status == UPLOAD_FILE_WRITE) {
        if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
            Update.printError(Serial);
        }
    } 
    else if (upload.status == UPLOAD_FILE_END) {
        if (Update.end(true)) {
            Serial.printf("Update Success: %u bytes\nRebooting...\n", upload.totalSize);
            ESP.restart();
        } 
        else {
            Update.printError(Serial);
        }
    }
}

void connectToWiFi() {
  int retries = 0;
  Serial.println("Connecting to WiFi...");
  
  WiFi.begin(config.ssid, config.password);
  
  while (WiFi.status() != WL_CONNECTED && retries < MAX_WIFI_RETRIES) {
    delay(WIFI_RETRY_DELAY);
    Serial.print(".");
    retries++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\nWiFi connected");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nFailed to connect to WiFi");
  }
}

void readAndSendSensorData() {
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("Failed to read from DHT sensor!");
    return;
  }
  
  // Use dynamic JSON document with specific size
  StaticJsonDocument<256> doc;
  doc["device_id"] = config.deviceId;
  doc["temperature"] = serialized(String(temperature, 1));  // Limit decimal places
  doc["humidity"] = serialized(String(humidity, 1));
  doc["timestamp"] = getTimestamp();
  doc["firmware_version"] = currentFirmwareVersion;
  
  // Clear the string before serializing
  String jsonString;
  jsonString.reserve(256);  // Pre-allocate memory
  serializeJson(doc, jsonString);
  
  if (wifiConnected) {
    sendDataToServer(jsonString);
  } else {
    Serial.println("Cannot send data - WiFi not connected");
  }
  
  // Cleanup
  jsonString = "";  // Free memory
}

void sendDataToServer(String jsonPayload) {
  if (!wifiConnected) {
    Serial.println("Cannot send data - WiFi not connected");
    return;
  }
  
  WiFiClient client;
  HTTPClient http;
  
  // Use begin with WiFiClient for better memory management
  if (http.begin(client, config.serverUrl)) {
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(10000);  // Increased timeout to 10 seconds
    
    Serial.println("Sending data: " + jsonPayload);
    
    int httpResponseCode = http.POST(jsonPayload);
    
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.print("HTTP Response code: ");
      Serial.println(httpResponseCode);
      // Only print response if it's not too long
      if (response.length() < 200) {
        Serial.print("Response: ");
        Serial.println(response);
      }
    } else {
      Serial.print("Error code: ");
      Serial.println(httpResponseCode);
      Serial.print("Error: ");
      Serial.println(http.errorToString(httpResponseCode));
    }
    
    http.end();
  } else {
    Serial.println("Unable to connect to server");
  }
  
  client.stop();  // Explicitly close the connection
}

void checkForUpdates() {
  if (!wifiConnected) return;
  
  HTTPClient http;
  String url = String(updateCheckUrl) + "?device_id=" + config.deviceId + 
               "&current_version=" + currentFirmwareVersion;
  
  http.begin(url);
  int httpResponseCode = http.GET();
  
  if (httpResponseCode == 200) {
    String response = http.getString();
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, response);
    
    if (!error) {
      bool updateAvailable = doc["update_available"];
      if (updateAvailable) {
        String newVersion = doc["new_version"];
        String firmwareUrl = doc["firmware_url"];
        
        Serial.println("Update available: " + newVersion);
        Serial.println("Downloading from: " + firmwareUrl);
        
        performOTAUpdate(firmwareUrl);
      } else {
        Serial.println("Firmware is up to date");
      }
    }

    if (error) {
    Serial.println("Failed to parse JSON");
    return;
  }

  }
  
  http.end();
}

void performOTAUpdate(String firmwareUrl) {
  Serial.println("Starting OTA update...");
  
  WiFiClient client;
  
  t_httpUpdate_return ret = httpUpdate.update(client, firmwareUrl);
  
  switch(ret) {
    case HTTP_UPDATE_FAILED:
      Serial.printf("HTTP_UPDATE_FAILED Error (%d): %s\n", 
                    httpUpdate.getLastError(), 
                    httpUpdate.getLastErrorString().c_str());
      break;
      
    case HTTP_UPDATE_NO_UPDATES:
      Serial.println("HTTP_UPDATE_NO_UPDATES");
      break;
      
    case HTTP_UPDATE_OK:
      Serial.println("HTTP_UPDATE_OK");
      ESP.restart();
      break;
  }
}

String getTimestamp() {
  time_t now;
  time(&now);
  // Add your local time offset (e.g., +5 hours for Pakistan)
  now += 5 * 3600;  // 5 hours * 3600 seconds/hour
  char buf[sizeof "2011-10-08T07:07:09+05:00"];
  strftime(buf, sizeof buf, "%FT%T+05:00", gmtime(&now));
  return String(buf);
}

uint32_t calculateChecksum(Config *cfg) {
  uint32_t checksum = 0;
  uint8_t *data = (uint8_t*)cfg;
  for (size_t i = 0; i < sizeof(Config) - sizeof(uint32_t); i++) {
    checksum += data[i];
  }
  return checksum;
}

void loadConfig() {
  EEPROM.get(0, config);
  
  if (config.checksum != calculateChecksum(&config)) {
    Serial.println("Invalid configuration, using defaults");
    strcpy(config.ssid, ssid);
    strcpy(config.password, password);
    strcpy(config.serverUrl, serverUrl);
    strcpy(config.deviceId, deviceId);
    saveConfig();
  }
}

void saveConfig() {
  config.checksum = calculateChecksum(&config);
  EEPROM.put(0, config);
  EEPROM.commit();
  Serial.println("Configuration saved");
}