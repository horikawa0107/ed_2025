import asyncio
from bleak import BleakScanner
import json
import pandas as pd
from datetime import datetime
from threading import Thread
    # APIリクエストに必要なライブラリ
import requests
from flask import Flask, render_template
import mysql.connector
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import time
import threading

app = Flask(__name__)
OMRON_ADDRESS = "7CCA64BD-C54C-EB8E-29D4-2531E81E0D6A"
OMRON_MANUFACTURER_ID = 725
ERROR_LOG_FILE = "errors.json"
API_URL = 'https://weather.tsukumijima.net/api/forecast/city/400040'
UPDATE_INTERVAL = 300  # 1時間ごとに再学習

# 2. MySQLからデータを読み込み（前処理済みテーブル）
def load_data_from_mysql():
    conn = get_db_connection()
    query = """
        SELECT temperature , humidity, light, pressure,  sound_level , discomfort_index, month 
        FROM sensor_data;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def train_and_save_model():
    current_time= datetime.now()
    # --- データ取得 ---
    df = load_data_from_mysql()
    print(df)
    if df.empty:
        print("データがありません。学習をスキップします。")
        return
    
    # --- 特徴量と目的変数に分割 ---
    features = ['temperature', 'humidity', 'light', 'pressure', 'sound_level', 'month']
    X = df[features]
    y = df['discomfort_index']
    
    # --- 学習用・テスト用データに分割 ---
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train, y_train)
    
    joblib.dump(model, "/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/models/comfort_score_rf_model.pkl")

    print("モデルを更新しました")

def background_training():
    """一定時間ごとに再学習"""
    while True:
        process_data_if_needed()
        # train_and_save_model()
        time.sleep(UPDATE_INTERVAL)

def predict_comfort_score(sensor_data):
    try:
        model = joblib.load("/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/models/comfort_score_rf_model.pkl")
        current_month = datetime.now().month  
        new_data = pd.DataFrame([{
            'avg_temperature': sensor_data["temperature"],
            'avg_humidity': sensor_data["humidity"],
            'avg_light': sensor_data["light"],
            'avg_pressure': sensor_data["pressure"],
            'avg_sound_level': sensor_data["sound_level"],
            'avg_month': current_month
        }])
        prediction = model.predict(new_data)
        return float(prediction[0])
    except Exception as e:
        log_error(f"予測に失敗: {str(e)}")
        return None
    
# def predict_comfort_score(sensor_data):
    # try:
    #     # 現在の月を取得
    #     current_month = datetime.now().month  
    #     # 新しいデータ
    #     new_data = pd.DataFrame([{
    #         'avg_temperature': sensor_data["temperature"],
    #         'avg_humidity': sensor_data["humidity"],
    #         'avg_light': sensor_data["light"],
    #         'avg_pressure': sensor_data["pressure"],
    #         'avg_sound_level': sensor_data["sound_level"],
    #         'avg_month': current_month
    #     }])
    #     prediction = model_pkl.predict(new_data)
    #     return float(prediction[0])
    # except Exception as e:
    #     log_error(f"予測に失敗: {str(e)}")
    #     return None

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='flask_db'
    )


def process_data_if_needed():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # データ数をチェック
    # cursor.execute("SELECT COUNT(*) AS count FROM sensor_data")
    # count = cursor.fetchone()['count']


    # if count < 100:
    #       print(f"データ数が少ないため処理をスキップします ({count} 件)")
    #       cursor.close()
    #       conn.close()
    #       return

    # print(f"{count} 件のデータを確認。前処理を開始します...")

    # すべてのデータを取得
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC limit 15")

    all_rows = cursor.fetchall()
    print(all_rows[0])
    cursor.close()

    avg_cursor = conn.cursor()

    for i in range(0, len(all_rows), 3):
        chunk = all_rows[i:i+3]
        if len(chunk) < 3:
            continue  # 3件未満は無視

        # 平均計算
        avg_data = {
            'timestamp': chunk[0]['timestamp'],  # 最初の時刻を使う
            'avg_temperature': sum(d['temperature'] for d in chunk) / 3,
            'avg_humidity': sum(d['humidity'] for d in chunk) / 3,
            'avg_light': sum(d['light'] for d in chunk) // 3,
            'avg_pressure': sum(d['pressure'] for d in chunk) / 3,
            'avg_sound_level': sum(d['sound_level'] for d in chunk) / 3,
            'avg_discomfort_index': sum(d['discomfort_index'] for d in chunk) / 3,
            'avg_battery': sum(d['battery'] for d in chunk) / 3,
            'avg_month': sum(d['month'] for d in chunk) / 3
        }

        # INSERT
        avg_cursor.execute("""
            INSERT INTO sensor_data_avg (
                timestamp, avg_temperature, avg_humidity, avg_light,  avg_pressure,
                avg_sound_level, avg_discomfort_index,  avg_battery ,avg_month
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s ,%s)
        """, (
            avg_data['timestamp'], avg_data['avg_temperature'], avg_data['avg_humidity'],
            avg_data['avg_light'],  avg_data['avg_pressure'],
            avg_data['avg_sound_level'], avg_data['avg_discomfort_index'],
            avg_data['avg_battery'],avg_data['avg_month']
        ))

    conn.commit()
    avg_cursor.close()
    conn.close()
    print("区間平均の計算と保存が完了しました。")


def api_request():
    try:
        tenki_data = requests.get(API_URL).json()
        temp = tenki_data['forecasts'][0]["image"]["width"]
        if temp is None:
            log_error("天気APIから気温データが取得できませんでした。")
            return 0  # デフォルト値を返す or None を返して後で処理する
        return temp
    except Exception as e:
        log_error(f"天気APIリクエスト失敗: {str(e)}")
        return 0
    
def parse_format_04(data: bytes):
    if len(data) < 20:
        return None
    return {
        "month":datetime.now().month,
        "timestamp": datetime.now(),
        "temperature": (int.from_bytes(data[1:3], 'little', signed=True) / 100),
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

def insert_data_to_learning_db(data,api_data):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
        INSERT INTO sensor_data
        (timestamp, month,  device_count,temperature, humidity, light, uv_index, pressure, sound_level, discomfort_index, heatstroke_risk, vibration, battery)
        VALUES (%s, %s , %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        data["timestamp"], data["month"],api_data,data["temperature"], data["humidity"], data["light"], data["uv_index"],
        data["pressure"], data["sound_level"], data["discomfort_index"], data["heatstroke_risk"],
        data["vibration"], data["battery"]
    ))
    connection.commit()
    cursor.close()
    connection.close()

def insert_data_to_predicted_db(data, comfort_score):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
        INSERT INTO predicted_data
        (timestamp, month,  temperature, humidity, light, pressure, sound_level, comfort_index, battery)
        VALUES (%s, %s , %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        data["timestamp"], data["month"],data["temperature"], data["humidity"], data["light"], 
        data["pressure"], data["sound_level"],  comfort_score, data["battery"]
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
                    api_data=int(api_request())
                    print(f"[SUCCESS] データ取得成功: {parsed}")  # ← 成功時はprintに変更
                    if parsed:
                        insert_data_to_learning_db(parsed,api_data)
                        discomfort_score = predict_comfort_score(parsed)
                        insert_data_to_predicted_db(parsed,discomfort_score)
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
     # データ件数を取得
    cursor.execute("SELECT COUNT(*) AS cnt FROM sensor_data")
    count = cursor.fetchone()["cnt"]
    cursor.close()
    connection.close()
    return render_template('index.html', data=rows,count=count)

@app.route('/predicted')
def show_predicted():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM predicted_data ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    connection.close()
    return render_template('use_model_index.html', data=row)



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
    thread = threading.Thread(target=background_training, daemon=True)
    thread.start()
    ble_thread = Thread(target=run_ble_loop)
    ble_thread.daemon = True
    ble_thread.start()
    app.run(host='0.0.0.0', port=5001)