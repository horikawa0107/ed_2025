import asyncio
from bleak import BleakScanner
import json
from datetime import datetime
import asyncio
from bleak import BleakScanner
import json
import pandas as pd
from datetime import datetime
from threading import Thread
    # APIリクエストに必要なライブラリ
import requests
from flask import Flask, render_template,redirect,request
import mysql.connector
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import time
import threading
import random

OMRON_ADDRESS = "7CCA64BD-C54C-EB8E-29D4-2531E81E0D6A"
OMRON_MANUFACTURER_ID = 725
ERROR_LOG_FILE = "errors.json"
API_URL = 'https://weather.tsukumijima.net/api/forecast/city/400040'
UPDATE_INTERVAL = 300  # ごとに再学習


def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='ed_2025'
    )

def parse_format_04(data: bytes):
    if len(data) < 20:
        return None
    return {
        "month":datetime.now().month,
        "timestamp": datetime.now(),
        "format_type": data[0],
        "temperature": (int.from_bytes(data[1:3], 'little', signed=True) / 100),
        "humidity": int.from_bytes(data[3:5], 'little') / 100,
        "light": int.from_bytes(data[5:7], 'little'),
        "uv_index": int.from_bytes(data[7:9], 'little') / 100,
        "pressure": int.from_bytes(data[9:11], 'little') / 10,
        "sound_level": int.from_bytes(data[11:13], 'little') / 100,
        "battery": data[19] * 0.01
    }

async def scan_once():
    scanner = BleakScanner()
    await scanner.start()
    await asyncio.sleep(20.0)  # スキャン時間
    await scanner.stop()
    return scanner.discovered_devices_and_advertisement_data




def insert_data_to_sensor_table(data,device_count,room_id="room_001"):
    connection = get_db_connection()
    cursor = connection.cursor()
    random_device_count=random.randint(device_count-2, device_count+2)
    query = """
        INSERT INTO sensor_data
        (timestamp, room_id,temperature, humidity, pressure,light, sound_level, device_count,month, battery)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
    """
    cursor.execute(query, (
        data["timestamp"], room_id,data["temperature"], data["humidity"],
        data["pressure"], data["light"],data["sound_level"], random_device_count,
        data["month"], data["battery"]
    ))
    connection.commit()
    cursor.close()
    connection.close()

error_log = []

def api_request():
    try:
        tenki_data = requests.get(API_URL).json()
        temp = tenki_data['forecasts'][1]['temperature']['max']['celsius']
        if temp is None:
            log_error("天気APIから気温データが取得できませんでした。")
            return 0  # デフォルト値を返す or None を返して後で処理する
        return temp
    except Exception as e:
        log_error(f"天気APIリクエスト失敗: {str(e)}")
        return 0

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
                    api_data=int(api_request())
                    print(f"[SUCCESS] データ取得成功: {parsed}")  # ← 成功時はprintに変更
                    if parsed:
                        insert_data_to_sensor_table(parsed,api_data)
                        print("データ保存成功")
                    else:
                        log_error("データフォーマットの解析に失敗しました。")
                else:
                    log_error("Manufacturer data が見つかりません。")
        except Exception as e:
            log_error(f"スキャン中に例外発生: {str(e)}")

        await asyncio.sleep(interval)

asyncio.run(periodic_scan(interval=30))



