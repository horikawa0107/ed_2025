import asyncio
from bleak import BleakScanner
import json
import gc
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import jsonify
import requests
import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error
from flask import Flask, render_template,redirect,request
import mysql.connector
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import time
import threading
import random

app = Flask(__name__)
# 🔽 ここでデータベースから取得して変数にセット

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='ed_2025'
    )

# 🔽 追加: room_infoテーブルからBLEアドレス（学習用）を取得する関数
def get_ble_address_capacity_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ble_address,capacity,mist_ap_address FROM room_info WHERE room_type = %s", (0,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        return result[0],result[1],result[2]
    else:
        raise ValueError("基準の部屋のble_addressが見つかりません。")

def get_ble_address_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ble_address,id FROM room_info")
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    if result:
        return result
    else:
        raise ValueError("他のroom_idのble_addressが見つかりません。")


OMRON_ADDRESS_FOR_ML,CAPACITY,MIST_AP_ADDRESS = get_ble_address_capacity_from_db()
# DBからBLEアドレスとroom_idを取得
rows = get_ble_address_from_db()
parsed_counts = {}  # ← omron_addressごとのカウントを保持する辞書

# rows: [(ble_address, id), (ble_address, id), ...]
OMRON_ADDRESSES = tuple([row[0] for row in rows])
ROOM_IDS        = tuple([row[1] for row in rows])

print(f"使用する学習用のOMRON BLEアドレス: {OMRON_ADDRESS_FOR_ML}")
print(f"使用する収容人数: {CAPACITY}")
print(f"使用するMIST AP: {MIST_AP_ADDRESS}")
print(f"使用するサービス運用用のOMRON BLEアドレス: {OMRON_ADDRESSES}")
print(f"使用するサービス運用用のroom_id: {ROOM_IDS}")

#パスは各自の環境に設定する
MODEL_PATH="/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/models/comfort_model_xgb.pkl"
OMRON_MANUFACTURER_ID = 725
ERROR_LOG_FILE = "/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/errors.json"
API_URL = 'https://weather.tsukumijima.net/api/forecast/city/400040'
#------------MIST API------------
API_TOKEN = "ycQduGG1tfVDuCYRdQDbMPoO2qU66UdD8e2xmIeWSHXQ81ZZxSzHYD5w85vCcKiDbL6lWTbwT124q9EnGTlO6fay6X08KF0w"
# ORG_ID = "14e64971-8492-40c9-9b5f-c169ea5c6903"
ORG_ID = "0ec9ad75-1ae0-40b3-bbd8-63ac91775547"
# SITE_ID = "b9b7b9d1-4823-465c-9bcf-14a0659003c6"
SITE_ID="22968ecf-ae7b-4d84-8100-670bb522267b"
# AP_ID = "00000000-0000-0000-1000-5c5b353ecdc3"
AP_ID = "00000000-0000-0000-1000-5c5b353ecdd7"

#---------------------------------
UPDATE_INTERVAL = 300  # 5分ごとに再学習



# 2. MySQLからデータを読み込み（前処理済みテーブル）
def load_data_from_mysql():
    print("processed_sensor_data_for_mlから読み込み")
    conn = get_db_connection()
    query = """
        SELECT avg_temperature, avg_humidity, avg_light, avg_pressure, avg_sound_level, month, score_from_avg_device_count
        FROM processed_sensor_data_for_ml
        ORDER BY timestamp DESC limit 5;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_lateset_processed_sensor_data():
    print("processed_sensor_dataから読み込み")
    conn = get_db_connection()
    query = """
        SELECT id,avg_temperature, avg_humidity, avg_light, avg_pressure, avg_sound_level, month
        FROM processed_sensor_data
        ORDER BY timestamp DESC limit 1;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df



def train_and_save_model(load_data_func=None):
    current_time = datetime.now()

    # --- データ取得 ---
    if load_data_func is None:
        df = load_data_from_mysql()
    else:
        df = load_data_func()
    print(f"processed_sensor_data_for_ml: {df}")
    if df.empty or len(df) < 5:
        print(f"{current_time}時点でデータが足りません。学習をスキップします。")
        return

    # --- 必須カラムチェック（テストで KeyError を期待） -------------------------------
    try:
        required_columns = [
            'avg_temperature',
            'avg_humidity',
            'avg_light',
            'avg_pressure',
            'avg_sound_level',
            'month',
            'score_from_avg_device_count'
        ]
        df = df[required_columns]
    except Exception as e:
        raise KeyError


    # --- 特徴量と目的変数に分割 ---
    features = [
        'avg_temperature',
        'avg_humidity',
        'avg_light',
        'avg_pressure',
        'avg_sound_level',
        'month'
    ]
    X = df[features]
    y = df['score_from_avg_device_count']

    # --- 学習用・テスト用データに分割 ---
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # --- モデルのロード or 初期化 ---
    if os.path.exists(MODEL_PATH):
        print("既存モデルを読み込み、追加学習を実行します...")
        model = XGBRegressor()
        model.load_model(MODEL_PATH)
        model.fit(X_train, y_train, xgb_model=MODEL_PATH)  # ✅ 追加学習
    else:
        print("新規モデルを作成します...")
        model = XGBRegressor(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            objective='reg:squarederror',
            tree_method='hist'  # CPU向け高速学習
        )
        model.fit(X_train, y_train)

    # --- モデルの評価 ---
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)

    print("\n=== モデル評価結果 ===")
    print(f"R²スコア       : {r2:.4f}")
    print(f"平均絶対誤差 (MAE): {mae:.4f}")
    print(f"MSE (平方二乗誤差): {mse:.4f}")
    print("=====================\n")

    
    # --- 特徴量重要度の表示 ---
    importances = model.feature_importances_
    print("\n=== 特徴量の重要度 ===")
    for feature_name, importance in zip(features, importances):
        print(f"{feature_name}: {importance:.4f}")
    print("=======================\n")
    # --- モデルの保存 ---
    model.save_model(MODEL_PATH)
    print(f"✅ モデルを更新・保存しました:{MODEL_PATH}")


def predict_comfort_score(sensor_data):
    try:
        model = XGBRegressor()
        model.load_model(MODEL_PATH)
        # DataFrame型で来た場合はそのまま型変換
        # --- DataFrame作り直し（ここが重要）---
        if isinstance(sensor_data, pd.DataFrame):
            sensor_data = sensor_data.iloc[0].to_dict()  # 1行目を辞書に変換

        new_data = pd.DataFrame([{
            'avg_temperature': float(sensor_data["avg_temperature"]),
            'avg_humidity': float(sensor_data["avg_humidity"]),
            'avg_light': float(sensor_data["avg_light"]),
            'avg_pressure': float(sensor_data["avg_pressure"]),
            'avg_sound_level': float(sensor_data["avg_sound_level"]),
            'month': int(sensor_data["month"])
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
    

def count_long_connected_devices(api_token: str,
                                  site_id: str, 
                                  ap_id: str, 
                                  threshold_minutes: int = 5) -> int:
    """
    特定のAPに接続しているデバイスのうち、uptimeが指定時間以上のデバイス数を返す関数。

    Parameters:
        api_token (str): MIST APIトークン
        site_id (str): サイトID
        ap_id (str): APのID
        threshold_minutes (int): uptimeの閾値（分単位、デフォルト30分）

    Returns:
        int: uptimeが閾値以上のデバイス数
    """
    # url = f"https://api.ac2.mist.com/api/v1/sites/{site_id}/stats/clients"
    url = f"https://mist-api-wrapper.onrender.com/api/v1/sites/{site_id}/stats/clients"

    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return 0

    clients = response.json()

    # uptimeがthreshold_minutes分以上のデバイスをカウント
    threshold_seconds = threshold_minutes * 60
    long_connected_devices = [
        c for c in clients
        if c.get("ap_id") == ap_id and c.get("uptime", 0) >= threshold_seconds
    ]

    return len(long_connected_devices)

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

def insert_data_to_sensor_data_for_ml_table(data,device_count,room_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO sensor_data_for_ml
            (timestamp, room_id,temperature, humidity, pressure,light, sound_level, device_count,month, battery)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data["timestamp"], room_id,data["temperature"], data["humidity"],
            data["pressure"], data["light"],data["sound_level"], device_count,
            data["month"], data["battery"]
        ))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        log_error(f"insert_data_to_sensor_data_for_ml_table エラー: {e}")

    
def generate_advice(data: dict) -> str:
    month = data["month"]
    temp = data["temperature"]
    humidity = data["humidity"]
    pressure = data["pressure"]
    sound = data["sound_level"]
    light = data["light"]

    advice_list = []

    # --- 季節判定 ---
    # 春: 3-5, 夏: 6-8, 秋: 9-11, 冬: 12-2
    if month in [6, 7, 8]:
        season = "summer"
    elif month in [12, 1, 2]:
        season = "winter"
    elif month in [3, 4, 5]:
        season = "spring"
    else:
        season = "autumn"

    # --- 温度アドバイス ---
    if season == "summer":
        if temp >= 30:
            advice_list.append("室温が高く熱中症のリスクがあります。冷房を利用しましょう。")
        elif temp < 26:
            advice_list.append("やや涼しめの快適な室温です。")

    elif season == "winter":
        if temp < 18:
            advice_list.append("室温が低く寒く感じる可能性があります。暖房を使用してください。")
        elif temp >= 26:
            advice_list.append("室温がやや高めです。暖房の調整を検討しましょう。")

    elif season == "spring":
        if temp < 20:
            advice_list.append("少し肌寒いかもしれません。")

    elif season == "autumn":
        if temp > 27:
            advice_list.append("暑く感じるかもしれません。冷房の使用を検討してください。")

    # --- 音（騒音）アドバイス ---
    if sound > 70:
        advice_list.append("騒音レベルが高く、集中しにくい環境です。静かな場所への移動をおすすめします。")

    # --- 気圧アドバイス ---
    if pressure < 1000:
        advice_list.append("気圧が低く、頭痛やだるさを感じる人がいるかもしれません。")

    # --- 湿度アドバイス ---
    if season == "summer" and humidity > 70:
        advice_list.append("湿度が高く蒸し暑く感じるかもしれません。除湿器や冷房を使用してください。")

    if season == "winter" and humidity < 40:
        advice_list.append("湿度が低く乾燥しています。加湿器を使いましょう。")
    
    # --- 照度アドバイス ---
    if  light > 750:
        advice_list.append("少し眩しい環境です。窓を閉めたり、ライトを弱くした方がいいかもしれません。")
    elif light < 500:
        advice_list.append("暗くて見えにくい環境です。部屋の照明をつけたり、窓を開けましょう。")



    # --- 最終出力 ---
    if advice_list:
        return " ".join(advice_list)
    else:
        return "特になし"


def insert_data_to_sensor_data_table(data,room_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO sensor_data
            (timestamp, room_id,temperature, humidity, pressure,light, sound_level, month, battery)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data["timestamp"], room_id,data["temperature"], data["humidity"],
            data["pressure"], data["light"],data["sound_level"],
            data["month"], data["battery"]
        ))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        log_error(f"insert_data_to_sensor_data_table エラー: {e}")

    
def insert_comfort_data(data, comfort_score,room_id,processed_sensor_data_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO comfort_data (timestamp, room_id, score, advice,processed_sensor_data_id)
            VALUES (%s, %s, %s, %s,%s)
        """
        print(f"快適指数:{comfort_score}")
        # advice = "快適です" if comfort_score > 0.7 else "少し調整が必要です"
        advice = generate_advice(data)
        cursor.execute(query, (
            data["timestamp"], room_id, comfort_score, advice,processed_sensor_data_id
        ))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        log_error(f"insert_comfort_data エラー: {e}")


def background_training():
    """一定時間ごとに再学習"""
    while True:
        print("\n=== 自動メンテナンス開始 ===")
        cleanup_old_sensor_data()
        train_and_save_model()
        gc.collect()
        print("=== メンテナンス完了 ===\n")
        time.sleep(UPDATE_INTERVAL)





def process_sensor_data(omron_address, room_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 最新3件のデータ取得
        cursor.execute("SELECT * FROM sensor_data WHERE room_id = %s ORDER BY timestamp DESC LIMIT 3;", (room_id,))
        all_rows = cursor.fetchall()
        cursor.close()

        # データが3件未満ならスキップ
        if len(all_rows) < 3:
            log_error(f"{omron_address} の運用用データが3件未満のため、平均計算をスキップしました。({len(all_rows)}件)")
            if 'conn' in locals() and conn:
                conn.close()
            return

        # 平均値を算出
        avg_data = {
            'timestamp': all_rows[0]['timestamp'],  # 最新の時刻を使用
            'avg_temperature': round(sum(d['temperature'] for d in all_rows) / 3,1),
            'avg_humidity': round(sum(d['humidity'] for d in all_rows) / 3,1),
            'avg_light': round(sum(d['light'] for d in all_rows) / 3,1),
            'avg_pressure': round(sum(d['pressure'] for d in all_rows) / 3,1),
            'avg_sound_level': round(sum(d['sound_level'] for d in all_rows) / 3,1),
            'battery': all_rows[0]['battery'],
            'month': all_rows[0]['month'],
        }

        avg_cursor = conn.cursor()
        avg_cursor.execute("""
            INSERT INTO processed_sensor_data (
                timestamp, room_id, avg_temperature, avg_humidity, avg_pressure, avg_light,
                avg_sound_level, month, battery
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            avg_data['timestamp'], room_id,
            avg_data['avg_temperature'], avg_data['avg_humidity'],
            avg_data['avg_pressure'], avg_data['avg_light'],
            avg_data['avg_sound_level'],
            avg_data['month'], avg_data['battery']
        ))

        conn.commit()
        avg_cursor.close()
        conn.close()

        print(f"✅ {omron_address} の {avg_data['timestamp']} 区間平均を計算・保存しました。")

    except Exception as e:
        # --- エラー内容をログ出力 ---
        log_error(f"process_sensor_data中にエラー発生({omron_address}): {str(e)}")

        # DBを安全にクローズ（もし開いていたら）
        try:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'avg_cursor' in locals() and avg_cursor:
                avg_cursor.close()
            if 'conn' in locals() and conn:
                conn.close()
        except:
            pass


def process_sensor_data_for_ml(omron_address,room_id):
    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
    
        # すべてのデータを取得
        cursor.execute("SELECT * FROM sensor_data_for_ml ORDER BY timestamp DESC limit 3;")
        all_rows = cursor.fetchall()
        cursor.close()

        # データが3件未満ならスキップ
        if len(all_rows) < 3:
            log_error(f"{omron_address} の学習用データが3件未満のため、平均計算をスキップしました。({len(all_rows)}件)")
            if 'conn' in locals() and conn:
                conn.close()
            return
        
         # 3件未満は無視
        avg_device_count=sum(d['device_count'] for d in all_rows) / 3
        # 平均計算
        avg_data = {
            'timestamp': all_rows[0]['timestamp'],  # 最初の時刻を使う
            'avg_temperature': round(sum(d['temperature'] for d in all_rows) / 3,1),
            'avg_humidity': round(sum(d['humidity'] for d in all_rows) / 3,1),
            'avg_light': round(sum(d['light'] for d in all_rows) / 3,1),
            'avg_pressure': round(sum(d['pressure'] for d in all_rows) / 3,1),
            'avg_sound_level': round(sum(d['sound_level'] for d in all_rows) / 3,1),
            'avg_device_count':round(sum(d['device_count'] for d in all_rows) / 3,1),
            'battery': all_rows[0]['battery'],
            'month':all_rows[0]['month'],
            'score_from_avg_device_count':round(min((avg_device_count/2.5)/CAPACITY*100,100),1),
        }
        # INSERT
        avg_cursor = conn.cursor()
        avg_cursor.execute("""
            INSERT INTO processed_sensor_data_for_ml (
                timestamp, room_id,avg_temperature, avg_humidity,   avg_pressure,avg_light,
                avg_sound_level, avg_device_count, month,battery,score_from_avg_device_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s ,%s,%s,%s)
        """, (
            avg_data['timestamp'], room_id,avg_data['avg_temperature'], avg_data['avg_humidity'],
            avg_data['avg_pressure'],avg_data['avg_light'],  
            avg_data['avg_sound_level'], avg_data['avg_device_count'],
            avg_data['month'],avg_data['battery'],avg_data['score_from_avg_device_count']
        ))
        conn.commit()
        avg_cursor.close()
        conn.close()
        print(f"sensor_data_for_mlの{avg_data['timestamp']}区間平均の計算と保存が完了しました。")
    

    except Exception as e:
        # --- エラー内容をログ出力 ---
        log_error(f"process_sensor_data_for_ml中にエラー発生({omron_address}): {str(e)}")

        # DBを安全にクローズ（もし開いていたら）
        try:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'avg_cursor' in locals() and avg_cursor:
                avg_cursor.close()
            if 'conn' in locals() and conn:
                conn.close()
        except:
            pass   


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
parsed_counts = {}  # ← omron_addressごとのカウントを保持する辞書

async def periodic_scan(interval=60):
    while True:
        try:
            for omron_address,room_id in zip(OMRON_ADDRESSES, ROOM_IDS):
                print(f"📡{omron_address}をスキャン中..")
                scanner = BleakScanner()
                await scanner.start()
                await asyncio.sleep(20.0)
                await scanner.stop()
                devices_info = scanner.discovered_devices_and_advertisement_data
                

                if omron_address not in devices_info:
                    log_error(f"{omron_address}のデバイスが見つかりません。")
                    continue

                
                adv_data = devices_info[omron_address][1]
                raw_data = adv_data.manufacturer_data.get(OMRON_MANUFACTURER_ID)
                
                if not raw_data:
                    log_error(f"{omron_address}のManufacturer data が見つかりません。")
                    continue

                parsed = parse_format_04(raw_data)
                if not parsed:
                    log_error(f"{omron_address}のデータフォーマットの解析に失敗しました。")
                    continue

                # === データ取得成功 ===
                print(f"[SUCCESS] データ取得成功({omron_address}): {parsed}")

                # --- データ挿入と処理 ---
                if omron_address == OMRON_ADDRESS_FOR_ML:
                    try:
                        api_data= count_long_connected_devices(API_TOKEN, SITE_ID, AP_ID)
                        print(f"5分以上接続しているデバイス数: {api_data}")
                    except Exception as e:
                        print(f"MIST APIに接続できませんでした。")
                        api_data = int(api_request())

                    insert_data_to_sensor_data_for_ml_table(parsed, api_data, room_id)
                else:
                    insert_data_to_sensor_data_table(parsed, room_id)
                    
                # === カウント管理 ===
                parsed_counts[omron_address] = parsed_counts.get(omron_address, 0) + 1

                # 3回取得ごとに test() 実行
                if parsed_counts[omron_address] % 3 == 0:
                    print(f"✅ {omron_address}で3回データ取得完了")
                    if omron_address==OMRON_ADDRESS_FOR_ML:
                        print("process_sensor_data_for_ml")
                        process_sensor_data_for_ml(omron_address,room_id)
                    else:
                        print("process_sensor_data")
                        process_sensor_data(omron_address,room_id)
                        lateset_processed_sensor_data=get_lateset_processed_sensor_data()
                        print(f"lateset_processed_sensor_data: {lateset_processed_sensor_data}")
                        current_time = datetime.now()
                        if lateset_processed_sensor_data.empty:
                            print(f"{current_time}時点でprocessed_sensor_dataにデータが足りません。予測をスキップします。")
                        else:
                            # 最新行を辞書形式で取得
                            features = [
                                'avg_temperature',
                                'avg_humidity',
                                'avg_light',
                                'avg_pressure',
                                'avg_sound_level',
                                'month'
                            ]
                            latest_row = lateset_processed_sensor_data.iloc[0][features]
                            comfort_score = predict_comfort_score(latest_row)
                        # --- 特徴量と目的変数に分割 ---
    
                        if comfort_score is not None:
                            print(f"予測快適指数: {comfort_score}")
                            id_value = int(lateset_processed_sensor_data["id"].iloc[0])

                            insert_comfort_data(parsed, comfort_score, room_id, id_value)
                        else:
                            print("予測に失敗しました。")
        except Exception as e:
            log_error(f"スキャン中に例外発生: {str(e)}")

        await asyncio.sleep(interval)


def cleanup_old_sensor_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        tables = [
            "sensor_data",
            "sensor_data_for_ml",
            "processed_sensor_data",
            "processed_sensor_data_for_ml",
            "comfort_data"
        ]

        for table in tables:
            delete_query = f"""
                DELETE FROM {table}
                WHERE timestamp < NOW() - INTERVAL 1 MONTH;
            """
            cursor.execute(delete_query)
            print(f"🧹 {table}: 古いデータを削除しました ({cursor.rowcount} 件)")

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ 1ヶ月以上前のセンサーデータ削除完了")

    except Exception as e:
        print(f"[ERROR] 自動削除中にエラー発生: {e}")

def run_ble_loop():
    asyncio.run(periodic_scan())


@app.route('/')
def home():
    connection = get_db_connection()  # データベース接続を取得
    cursor = connection.cursor()  # クエリを実行するためのカーソルを取得
    cursor.execute("SELECT id,room_name FROM room_info WHERE room_type = 1;")  # greetingsテーブルからmessage列を取得
    rooms = cursor.fetchall()  # 取得したメッセージをすべてリストで取得
    cursor.close()  # カーソルを閉じる
    connection.close()
    return render_template('select2.html' ,rooms=rooms)




#bleセンサーの記録を見る
@app.route("/look", methods=["POST"])
def move_display_page():
    room_id = request.form.get("room_id")
    room_name = request.form.get("room_name")
    print(f"受け取った room_id:{room_id} room_name:{room_name}")
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM comfort_data WHERE room_id = %s ORDER BY timestamp DESC LIMIT 1",
        (room_id,)
    )
    predicted_data = cursor.fetchone()
    print(f"predicted_data:{predicted_data}")
    processed_sensor_data_id=predicted_data["processed_sensor_data_id"]
    cursor.execute(
        "SELECT * FROM processed_sensor_data WHERE id = %s",
        (processed_sensor_data_id,)
    )
    latest_data = cursor.fetchone()
    cursor.execute(
        "SELECT * FROM processed_sensor_data WHERE room_id = %s ORDER BY timestamp DESC LIMIT 10",
        (room_id,)
    )    
    datas_for_log = cursor.fetchall()
     # データ件数を取得
    cursor.execute(
        "SELECT COUNT(*) AS cnt FROM processed_sensor_data WHERE room_id = %s",
        (room_id,)
    )
    data_count = cursor.fetchone()["cnt"]
    cursor.close()
    connection.close()
    return render_template('display2.html', 
                           room_id=room_id,
                           room_name=room_name,
                           predicted_data=predicted_data,
                           latest_data=latest_data,
                           datas_for_log=datas_for_log,
                           data_count=data_count)



@app.route("/api/latest/<int:room_id>")
def get_latest_data(room_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    # 最新の快適指数
    cursor.execute(
        "SELECT * FROM comfort_data WHERE room_id = %s ORDER BY timestamp DESC LIMIT 1",
        (room_id,)
    )
    
    predicted_data = cursor.fetchone()
    processed_sensor_data_id=predicted_data["processed_sensor_data_id"]
    # 最新データ
    cursor.execute(
        "SELECT * FROM processed_sensor_data WHERE id = %s",
        (processed_sensor_data_id,)
    )
    latest_data = cursor.fetchone()
    # データ件数
    cursor.execute(
        "SELECT COUNT(*) AS cnt FROM processed_sensor_data WHERE room_id = %s",
        (room_id,)
    )
    data_count = cursor.fetchone()["cnt"]
    # 最新10件のログ
    cursor.execute(
        "SELECT * FROM processed_sensor_data WHERE room_id = %s ORDER BY timestamp DESC LIMIT 10",
        (room_id,)
    )
    datas_for_log = cursor.fetchall()
    cursor.close()
    connection.close()

    return jsonify({
        "latest_data": latest_data,
        "predicted_data": predicted_data,
        "data_count": data_count,
        "datas_for_log":datas_for_log
    })

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