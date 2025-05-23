import mysql.connector
from datetime import datetime

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',  # または 'db' など、環境に応じて調整
        user='root',
        password='password',
        database='flask_db'
    )

def process_data_if_needed():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # データ数をチェック
    cursor.execute("SELECT COUNT(*) AS count FROM sensor_data")
    count = cursor.fetchone()['count']


    if count < 100:
          print(f"データ数が少ないため処理をスキップします ({count} 件)")
          cursor.close()
          conn.close()
          return

    print(f"{count} 件のデータを確認。前処理を開始します...")

    # すべてのデータを取得
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp ASC")

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

if __name__ == '__main__':
    process_data_if_needed()