import asyncio
from bleak import BleakScanner
import json
from datetime import datetime
from threading import Thread
    # APIリクエストに必要なライブラリ
import requests
from flask import Flask, render_template
import mysql.connector
import os

app = Flask(__name__)
OMRON_ADDRESS = "7CCA64BD-C54C-EB8E-29D4-2531E81E0D6A"
OMRON_MANUFACTURER_ID = 725
ERROR_LOG_FILE = "errors.json"
API_URL = 'https://weather.tsukumijima.net/api/forecast/city/400040'

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='flask_db'
    )

def api_request():
    # APIリクエストを送信
    tenki_data = requests.get(API_URL).json()
    # tenki_data = requests.get(url).json()
    return tenki_data['forecasts'][0]["temperature"]["max"]["celsius"]

def parse_format_04(data: bytes):
    if len(data) < 20:
        return None
    return {
        "month":datetime.now().month,
        "timestamp": datetime.now(),
        "temperature": (int.from_bytes(data[1:3], 'little', signed=True) / 100)-6,
        "humidity": int.from_bytes(data[3:5], 'little') / 100,
        "light": int.from_bytes(data[5:7], 'little'),
        "uv_index": int.from_bytes(data[7:9], 'little') / 100,
        "pressure": int.from_bytes(data[9:11], 'little') / 10,
        "sound_level": int.from_bytes(data[11:13], 'little') / 100,
        "discomfort_index": int.from_bytes(data[13:15], 'little') / 100,
        "heatstroke_risk": int.from_bytes(data[15:17], 'little') / 100,
        "vibration": int.from_bytes(data[17:19], 'little'),
        "battery": data[19] * 0.01
    }

def insert_data_to_db(data):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
        INSERT INTO sensor_data
        (timestamp, month,  temperature, humidity, light, uv_index, pressure, sound_level, discomfort_index, heatstroke_risk, vibration, battery)
        VALUES (%s, %s , %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        data["timestamp"], data["month"],data["temperature"], data["humidity"], data["light"], data["uv_index"],
        data["pressure"], data["sound_level"], data["discomfort_index"], data["heatstroke_risk"],
        data["vibration"], data["battery"]
    ))
    connection.commit()
    cursor.close()
    connection.close()

# エラーをファイルとリストに記録
error_log = []

def log_error(message):
    entry = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "error": message
    }
    error_log.append(entry)
    print(f"[ERROR] {entry}")
    # JSONファイルに追記保存
    if os.path.exists(ERROR_LOG_FILE):
        with open(ERROR_LOG_FILE, "r", encoding="utf-8") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []
    else:
        logs = []

    logs.append(entry)
    with open(ERROR_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

# BLEスキャン処理
async def periodic_scan(interval=30):
    while True:
        try:
            scanner = BleakScanner()
            await scanner.start()
            await asyncio.sleep(20.0)
            await scanner.stop()
            devices_info = scanner.discovered_devices_and_advertisement_data

            if OMRON_ADDRESS not in devices_info:
                log_error("デバイスが見つかりません。")
            else:
                adv_data = devices_info[OMRON_ADDRESS][1]
                raw_data = adv_data.manufacturer_data.get(OMRON_MANUFACTURER_ID)
                if raw_data:
                    parsed = parse_format_04(raw_data)
                    api_data=api_request()
                    log_error(api_data)
                    if parsed:
                        insert_data_to_db(parsed)
                    else:
                        log_error("データフォーマットの解析に失敗しました。")
                else:
                    log_error("Manufacturer data が見つかりません。")
        except Exception as e:
            log_error(f"スキャン中に例外発生: {str(e)}")

        await asyncio.sleep(interval)

def run_ble_loop():
    asyncio.run(periodic_scan())

@app.route('/')
def home():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 10")
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('index.html', data=rows)

@app.route('/errors')
def show_errors():
    # 最新のエラーログを表示
    if os.path.exists(ERROR_LOG_FILE):
        with open(ERROR_LOG_FILE, "r", encoding="utf-8") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = [{"timestamp": "N/A", "error": "JSON decode error"}]
    else:
        logs = [{"timestamp": "N/A", "error": "エラーログファイルが存在しません"}]
    return render_template('errors.html', logs=logs)

if __name__ == '__main__':
    ble_thread = Thread(target=run_ble_loop)
    ble_thread.daemon = True
    ble_thread.start()
    app.run(host='0.0.0.0', port=5001)