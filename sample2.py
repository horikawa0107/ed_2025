import mysql.connector
from datetime import datetime, timedelta

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',  # または 'db'（Docker内）
        user='root',
        password='password',
        database='flask_db'
    )

def compute_interval_average(interval_minutes=5):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 最古と最新のタイムスタンプを取得
    cursor.execute("SELECT MIN(timestamp) as min_time, MAX(timestamp) as max_time FROM sensor_data")
    result = cursor.fetchone()
    min_time = result["min_time"]
    max_time = result["max_time"]

    if not min_time or not max_time:
        print("センサーデータがありません。")
        return

    current_start = min_time.replace(second=0, microsecond=0)
    interval = timedelta(minutes=interval_minutes)

    while current_start < max_time:
        current_end = current_start + interval

        cursor.execute("""
            SELECT
                AVG(temperature) as avg_temperature,
                AVG(humidity) as avg_humidity,
                AVG(light) as avg_light,
                AVG(uv_index) as avg_uv_index,
                AVG(pressure) as avg_pressure,
                AVG(sound_level) as avg_sound_level,
                AVG(discomfort_index) as avg_discomfort_index,
                AVG(heatstroke_risk) as avg_heatstroke_risk,
                AVG(vibration) as avg_vibration,
                AVG(battery) as avg_battery
            FROM sensor_data
            WHERE timestamp >= %s AND timestamp < %s
        """, (current_start, current_end))

        avg_result = cursor.fetchone()

        if avg_result["avg_temperature"] is not None:
            # 既にデータがあるか確認して重複挿入を防ぐ
            cursor.execute("SELECT 1 FROM averaged_data WHERE interval_start = %s", (current_start,))
            if cursor.fetchone() is None:
                cursor.execute("""
                    INSERT INTO averaged_data (
                        interval_start, avg_temperature, avg_humidity, avg_light, avg_uv_index,
                        avg_pressure, avg_sound_level, avg_discomfort_index, avg_heatstroke_risk,
                        avg_vibration, avg_battery
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    current_start,
                    avg_result["avg_temperature"],
                    avg_result["avg_humidity"],
                    avg_result["avg_light"],
                    avg_result["avg_uv_index"],
                    avg_result["avg_pressure"],
                    avg_result["avg_sound_level"],
                    avg_result["avg_discomfort_index"],
                    avg_result["avg_heatstroke_risk"],
                    avg_result["avg_vibration"],
                    avg_result["avg_battery"]
                ))
                conn.commit()

        current_start = current_end

    cursor.close()
    conn.close()
    print("区間平均の計算と保存が完了しました。")

# 実行
compute_interval_average(interval_minutes=5)