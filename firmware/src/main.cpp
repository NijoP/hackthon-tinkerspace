#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_camera.h"
#include "secrets.h"

#ifndef SERVER_PATH
#define SERVER_PATH "/api/frame"
#endif

#ifndef DEVICE_ID
#define DEVICE_ID "esp32-kitchen-cam"
#endif

// Seeed XIAO ESP32-S3 Sense camera pins commonly used by Seeed examples.
// Verify the exact physical board/camera variant before flashing.
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  10
#define SIOD_GPIO_NUM  40
#define SIOC_GPIO_NUM  39
#define Y9_GPIO_NUM    48
#define Y8_GPIO_NUM    11
#define Y7_GPIO_NUM    12
#define Y6_GPIO_NUM    14
#define Y5_GPIO_NUM    16
#define Y4_GPIO_NUM    18
#define Y3_GPIO_NUM    17
#define Y2_GPIO_NUM    15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM  47
#define PCLK_GPIO_NUM  13

static unsigned long lastUploadMs = 0;
static const unsigned long uploadIntervalMs = 333; // quality-preserving low-latency mode: ~3 FPS, newest frame only
static String selectedSsid = WIFI_SSID;
static uint32_t uploadedFrameCount = 0;

String serverUrl() {
  return String("http://") + SERVER_HOST + ":" + String(SERVER_PORT) + SERVER_PATH;
}

void scanWifiOnce() {
  Serial.println("Scanning Wi-Fi networks...");
  int n = WiFi.scanNetworks();
  if (n <= 0) {
    Serial.println("No Wi-Fi networks found. Check hotspot is on and set to 2.4 GHz / compatibility mode.");
    return;
  }
  for (int i = 0; i < n; i++) {
    String ssid = WiFi.SSID(i);
    Serial.printf("Network %d: %s RSSI=%d channel=%d encryption=%d length=%d\n", i + 1, ssid.c_str(), WiFi.RSSI(i), WiFi.channel(i), WiFi.encryptionType(i), ssid.length());
    if (ssid == WIFI_SSID || ssid.startsWith(WIFI_SSID)) {
      selectedSsid = ssid;
    }
  }
}

bool connectWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  Serial.print("Connecting to configured Wi-Fi SSID: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.disconnect(true);
  delay(300);
  scanWifiOnce();
  Serial.print("Using scanned SSID length: ");
  Serial.println(selectedSsid.length());
  WiFi.begin(selectedSsid.c_str(), WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Wi-Fi connected. Device IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }

  Serial.printf("Wi-Fi connection failed; status=%d. Will retry.\n", WiFi.status());
  return false;
}

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_VGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 2;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return false;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor) {
    sensor->set_framesize(sensor, FRAMESIZE_VGA);
    sensor->set_quality(sensor, 12);
  }

  Serial.println("Camera initialized.");
  return true;
}

bool uploadFrame() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  if (strlen(SERVER_HOST) == 0) {
    Serial.println("SERVER_HOST is empty. Set laptop LAN IP in firmware/include/secrets.h before flashing.");
    delay(2000);
    return false;
  }

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed.");
    return false;
  }

  HTTPClient http;
  http.setTimeout(300);
  http.begin(serverUrl());
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-Device-Id", DEVICE_ID);
  http.addHeader("X-Frame-Count", String(uploadedFrameCount + 1));
  http.addHeader("X-Capture-Millis", String(millis()));
  int code = http.POST(fb->buf, fb->len);
  uploadedFrameCount++;
  if (code > 0) {
    if (uploadedFrameCount % 30 == 0) {
      Serial.printf("Uploaded frame #%lu: %u bytes, HTTP %d\n", (unsigned long)uploadedFrameCount, fb->len, code);
    }
  } else {
    Serial.printf("Frame upload failed: %s\n", http.errorToString(code).c_str());
  }
  http.end();
  esp_camera_fb_return(fb);
  return code >= 200 && code < 300;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("AI Kitchen Assistant camera node starting...");
  Serial.print("Device ID: ");
  Serial.println(DEVICE_ID);
  Serial.print("Upload URL: ");
  Serial.println(serverUrl());
  connectWifi();
  initCamera();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
    delay(1000);
    return;
  }

  if (millis() - lastUploadMs >= uploadIntervalMs) {
    lastUploadMs = millis();
    uploadFrame();
  }
}
