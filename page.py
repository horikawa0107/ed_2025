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

app = Flask(__name__)
OMRON_ADDRESS = "7CCA64BD-C54C-EB8E-29D4-2531E81E0D6A"
OMRON_MANUFACTURER_ID = 725
ERROR_LOG_FILE = "errors.json"
API_URL = 'https://weather.tsukumijima.net/api/forecast/city/400040'
UPDATE_INTERVAL = 300  # 1時間ごとに再学習


def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='ed_2025'
    )

# 2. MySQLからデータを読み込み（前処理済みテーブル）
def load_data_from_mysql():
    conn = get_db_connection()
    query = """
        SELECT avg_temperature, avg_humidity, avg_light, avg_pressure, avg_sound_level, avg_month, score_from_avg_device_count
        FROM processed_sensor_data;
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
    features = ['avg_temperature', 'avg_humidity', 'avg_light', 'avg_pressure', 'avg_sound_level', 'avg_month']
    X = df[features]
    y = df['score_from_avg_device_count']
    
    # --- 学習用・テスト用データに分割 ---
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train, y_train)
    
    joblib.dump(model, f"/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/models/rf_model.pkl")

    print("モデルを更新しました")

def predict_comfort_score(sensor_data):
    try:
        model = joblib.load("/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/models/rf_model.pkl")
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
    

def parse_format_04(data: bytes):
    if len(data) < 20:
        return None
    return {
        "month":datetime.now().month,
        "timestamp": datetime.now(),
        "temperature": (int.from_bytes(data[1:3], 'little', signed=True) / 100),
        "humidity": int.from_bytes(data[3:5], 'little') / 100,
        "light": int.from_bytes(data[5:7], 'little'),
        "pressure": int.from_bytes(data[9:11], 'little') / 10,
        "sound_level": int.from_bytes(data[11:13], 'little') / 100,
        "battery": data[19] * 0.01
    }

def insert_data_to_sensor_table(data,device_count):
    connection = get_db_connection()
    random_device_count=random.randint(device_count-2, device_count+2)
    cursor = connection.cursor()
    query = """
        INSERT INTO sensor_data
        (timestamp, room_id,temperature, humidity, pressure,light, sound_level, device_count,month, battery)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        data["timestamp"], "room_001",data["temperature"], data["humidity"],
        data["pressure"], data["light"],data["sound_level"], random_device_count,
        data["month"], data["battery"]
    ))
    connection.commit()
    cursor.close()
    connection.close()


def insert_comfort_data(data, comfort_score):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
        INSERT INTO comfort_data (timestamp, room_id, predicted_score, advice)
        VALUES (%s, %s, %s, %s)
    """
    advice = "快適です" if comfort_score > 0.7 else "少し調整が必要です"
    cursor.execute(query, (
        data["timestamp"], "room_001", comfort_score, advice
    ))
    connection.commit()
    cursor.close()
    connection.close()

def background_training():
    """一定時間ごとに再学習"""
    while True:
        process_data_if_needed()
        train_and_save_model()
        time.sleep(UPDATE_INTERVAL)

def get_capacity(room_id="room_001"):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT capacity FROM room_info WHERE room_id=%s",(room_id,))
    capacity = cursor.fetchone()
    cursor.close()
    connection.close()
    return capacity[0]if capacity else None



def process_data_if_needed(room_id="room_001"):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # すべてのデータを取得
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC limit 15")

    all_rows = cursor.fetchall()
    print(all_rows[0])
    cursor.close()
    capacity=get_capacity()


    avg_cursor = conn.cursor()

    for i in range(0, len(all_rows), 3):
        chunk = all_rows[i:i+3]
        if len(chunk) < 3:
            continue  # 3件未満は無視
        avg_device_count=sum(d['battery'] for d in chunk) / 3

        # 平均計算
        avg_data = {
            'timestamp': chunk[0]['timestamp'],  # 最初の時刻を使う
            'avg_temperature': sum(d['temperature'] for d in chunk) / 3,
            'avg_humidity': sum(d['humidity'] for d in chunk) / 3,
            'avg_light': sum(d['light'] for d in chunk) // 3,
            'avg_pressure': sum(d['pressure'] for d in chunk) / 3,
            'avg_sound_level': sum(d['sound_level'] for d in chunk) / 3,
            'avg_device_count':sum(d['device_count'] for d in chunk) / 3,
            'avg_battery': sum(d['battery'] for d in chunk) / 3,
            'score_from_avg_device_count':(avg_device_count/2.5)/capacity*100,
            'avg_month': sum(d['month'] for d in chunk) / 3

        }

        # INSERT
        avg_cursor.execute("""
            INSERT INTO processed_sensor_data (
                timestamp, room_id,avg_temperature, avg_humidity,   avg_pressure,avg_light,
                avg_sound_level, avg_device_count, avg_month,score_from_avg_device_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s ,%s,%s)
        """, (
            avg_data['timestamp'], room_id,avg_data['avg_temperature'], avg_data['avg_humidity'],
            avg_data['avg_pressure'],avg_data['avg_light'],  
            avg_data['avg_sound_level'], avg_data['avg_device_count'],
            avg_data['avg_month'],avg_data['score_from_avg_device_count']
        ))

    conn.commit()
    avg_cursor.close()
    conn.close()
    print(f"{avg_data['timestamp']}区間平均の計算と保存が完了しました。")



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
                        insert_data_to_sensor_table(parsed,api_data)
                        discomfort_score = predict_comfort_score(parsed)
                        insert_comfort_data(parsed,discomfort_score)
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
    cursor.execute("SELECT room_name, capacity, floor FROM room_info;")  # greetingsテーブルからmessage列を取得
    rooms = cursor.fetchall()  # 取得したメッセージをすべてリストで取得
    cursor.close()  # カーソルを閉じる
    connection.close()
    return render_template('select.html' ,rooms=rooms)


#部屋の登録ページへ遷移する処理
@app.route("/register", methods=["POST"])
def move_register_page():
    connection = get_db_connection()  # データベース接続を取得
    cursor = connection.cursor()  # クエリを実行するためのカーソルを取得
    cursor.execute("SELECT room_name FROM room_info;")  # greetingsテーブルからmessage列を取得
    rooms = cursor.fetchall()  # 取得したメッセージをすべてリストで取得
    cursor.close()  # カーソルを閉じる
    connection.close()
    return render_template('register2.html', rooms=rooms)  # messagesをテンプレートに渡してHTMLをレンダリング

#部屋を登録する処理
@app.route('/add', methods=['POST'])
def add_message():
    # メッセージを追加する処理を行うルート（POSTリクエストを処理）
    room_name = request.form['room_name']  # フォームから送信されたメッセージを取得
    room_id = request.form['room_id']
    ble_address = request.form['ble_address']
    capacity = request.form['capacity']
    floor = request.form['floor']
    remarks= request.form['remarks']
    connection = get_db_connection()  # データベース接続を取得
    cursor = connection.cursor()  # クエリを実行するためのカーソルを取得
    cursor.execute("INSERT INTO room_info (room_id,room_name,ble_address,capacity,floor,remarks) VALUES (%s,%s,%s,%s,%s,%s)", (room_id,room_name,ble_address,capacity,floor,remarks))  # メッセージをgreetingsテーブルに挿入
    connection.commit()  # データベースに変更を反映
    cursor.execute("SELECT room_name FROM room_info")  # greetingsテーブルからmessage列を取得
    rooms = cursor.fetchall()  # 取得したメッセージをすべてリストで取得
    cursor.close()  # カーソルを閉じる
    connection.close()  # データベース接続を閉じる
    return render_template("register2.html",rooms=rooms)

#bleセンサーの記録を見る
@app.route("/look", methods=["POST"])
def move_display_page():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM comfort_data ORDER BY timestamp DESC LIMIT 1")
    predicted_data = cursor.fetchone()
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 10")
    latest_data = cursor.fetchall()
     # データ件数を取得
    cursor.execute("SELECT COUNT(*) AS cnt FROM sensor_data")
    data_count = cursor.fetchone()["cnt"]
    cursor.close()
    connection.close()
    return render_template('display2.html', predicted_data=predicted_data,latest_data=latest_data,data_count=data_count)




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