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

app = Flask(__name__)
OMRON_ADDRESS = "7CCA64BD-C54C-EB8E-29D4-2531E81E0D6A"
OMRON_MANUFACTURER_ID = 725
ERROR_LOG_FILE = "errors.json"
API_URL = 'https://weather.tsukumijima.net/api/forecast/city/400040'
model_pkl = joblib.load(open('/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/models/comfort_score_rf_model.pkl', 'rb'))
UPDATE_INTERVAL = 3600  # 1時間ごとに再学習


def predict_comfort_score(sensor_data):
    try:
        # 現在の月を取得
        current_month = datetime.now().month  
        # 新しいデータ
        new_data = pd.DataFrame([{
            'avg_temperature': sensor_data["temperature"],
            'avg_humidity': sensor_data["humidity"],
            'avg_light': sensor_data["light"],
            'avg_pressure': sensor_data["pressure"],
            'avg_sound_level': sensor_data["sound_level"],
            'avg_month': current_month
        }])
        prediction = model_pkl.predict(new_data)
        return float(prediction[0])
    except Exception as e:
        log_error(f"予測に失敗: {str(e)}")
        return None

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='flask_db'
    )

def room_id():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM predicted_data ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        connection.close()
        return render_template('display.html', data=row)
    except Exception as e:
        log_error(f"天気APIリクエスト失敗: {str(e)}")
        return 0

def api_request():
    try:
        tenki_data = requests.get(API_URL).json()
        temp = tenki_data['forecasts'][0]["temperature"]["max"]["celsius"]
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
                    if parsed and api_data:
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
    connection = get_db_connection()  # データベース接続を取得
    cursor = connection.cursor()  # クエリを実行するためのカーソルを取得
    cursor.execute("SELECT message FROM greetings")  # greetingsテーブルからmessage列を取得
    messages = cursor.fetchall()  # 取得したメッセージをすべてリストで取得
    cursor.close()  # カーソルを閉じる
    connection.close()
    return render_template('select.html' ,messages=messages)

#エラー表示ページの処理
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

#部屋の登録ページへ遷移する処理
@app.route("/register", methods=["POST"])
def move_register_page():
    connection = get_db_connection()  # データベース接続を取得
    cursor = connection.cursor()  # クエリを実行するためのカーソルを取得
    cursor.execute("SELECT message FROM greetings")  # greetingsテーブルからmessage列を取得
    messages = cursor.fetchall()  # 取得したメッセージをすべてリストで取得
    
    cursor.close()  # カーソルを閉じる
    connection.close()
    return render_template('register.html', messages=messages)  # messagesをテンプレートに渡してHTMLをレンダリング

#部屋を登録する処理
@app.route('/add', methods=['POST'])
def add_message():
    # メッセージを追加する処理を行うルート（POSTリクエストを処理）
    message = request.form['message']  # フォームから送信されたメッセージを取得
    connection = get_db_connection()  # データベース接続を取得
    cursor = connection.cursor()  # クエリを実行するためのカーソルを取得
    cursor.execute("INSERT INTO greetings (message) VALUES (%s)", (message,))  # メッセージをgreetingsテーブルに挿入
    connection.commit()  # データベースに変更を反映
    cursor.close()  # カーソルを閉じる
    connection.close()  # データベース接続を閉じる
    return render_template("register.html")

#bleセンサーの記録を見る
@app.route("/look", methods=["POST"])
def move_display_page():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM predicted_data ORDER BY timestamp DESC LIMIT 1")
    predicted_data = cursor.fetchone()
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 10")
    latest_data = cursor.fetchall()
     # データ件数を取得
    cursor.execute("SELECT COUNT(*) AS cnt FROM sensor_data")
    data_count = cursor.fetchone()["cnt"]
    cursor.close()
    connection.close()
    return render_template('display.html', predicted_data=predicted_data,latest_data=latest_data,data_count=data_count)

if __name__ == '__main__':
    ble_thread = Thread(target=run_ble_loop)
    ble_thread.daemon = True
    ble_thread.start()
    app.run(host='0.0.0.0', port=5001)