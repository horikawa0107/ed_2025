import mysql.connector
import pytest
from datetime import datetime
from page import (
    parse_format_04,
    insert_data_to_sensor_data_for_ml_table,
    insert_data_to_sensor_data_table
)

# ------- テスト用のraw_dataを作成 -------
def make_raw_data_for_ml():
    data = bytearray(20)
    data[1:3] = (2200).to_bytes(2, 'little', signed=True)     # temperature=25.00
    data[3:5] = (7000).to_bytes(2, 'little')                  # humidity=45.00
    data[5:7] = (110).to_bytes(2, 'little')                   # light=300
    data[9:11] = (10110).to_bytes(2, 'little')                # pressure=1012.5
    data[11:13] = (600).to_bytes(2, 'little')                 # sound=5.50
    data[19] = 179                                              # battery=0.95
    return bytes(data)

def make_raw_data():
    data = bytearray(20)
    data[1:3] = (2000).to_bytes(2, 'little', signed=True)     # temperature=25.00
    data[3:5] = (6700).to_bytes(2, 'little')                  # humidity=45.00
    data[5:7] = (130).to_bytes(2, 'little')                   # light=300
    data[9:11] = (10100).to_bytes(2, 'little')                # pressure=1012.5
    data[11:13] = (600).to_bytes(2, 'little')                 # sound=5.50
    data[19] = 170                                             # battery=0.95
    return bytes(data)

@pytest.fixture
def db_conn():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='ed_2025_test'
    )
    yield conn
    conn.close()


def test_st001_insert_sensor_data(db_conn):
    raw = make_raw_data()

    # --- 解析 ---
    parsed = parse_format_04(raw)
    assert parsed is not None, "parse_format_04で解析失敗"

    # --- sensor_data へ挿入 ---
    insert_data_to_sensor_data_table(parsed, room_id=1)

    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM sensor_data ORDER BY id DESC LIMIT 1;")
    row = cursor.fetchone()

    assert row is not None, "sensor_data にレコードが挿入されていない"
    assert row["room_id"] == 1
    assert row["temperature"] == parsed["temperature"]
    assert row["humidity"] == parsed["humidity"]


def test_st001_insert_sensor_data_for_ml(db_conn):
    raw = make_raw_data_for_ml()
    parsed = parse_format_04(raw)

    assert parsed is not None

    # --- ML用テーブルに挿入 ---
    insert_data_to_sensor_data_for_ml_table(parsed, device_count=10, room_id=2)

    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM sensor_data_for_ml ORDER BY id DESC LIMIT 1;")
    row = cursor.fetchone()
    
    assert row is not None, "sensor_data_for_ml にレコードが挿入されていない"
    assert row["room_id"] == 2
    assert row["temperature"] == parsed["temperature"]
    assert row["humidity"] == parsed["humidity"]
    assert row["light"] == parsed["light"]
