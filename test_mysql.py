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
from sklearn.ensemble import RandomForestRegressor
import joblib
import time
import threading
import random



def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='ed_2025'
    )
# 🔽 追加: room_infoテーブルからBLEアドレスを取得する関数
def get_ble_address_capacity_from_db(room_id=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ble_address,capacity,mist_ap_address FROM room_info WHERE id = %s", (room_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        return result[0],result[1],result[2]
    else:
        raise ValueError("指定したroom_idのble_addressが見つかりません。")

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


CAPACITY,OMRON_ADDRESS_FOR_ML,MIST_AP_ADDRESS = get_ble_address_capacity_from_db(1)
# DBからBLEアドレスとroom_idを取得
rows = get_ble_address_from_db()

# rows: [(ble_address, id), (ble_address, id), ...]
OMRON_ADDRESSES = tuple([row[0] for row in rows])
ROOM_IDS        = tuple([row[1] for row in rows])
print(f"使用する学習用のOMRON BLEアドレス: {OMRON_ADDRESS_FOR_ML}")
print(f"使用する収容人数: {CAPACITY}")
print(f"使用するMIST AP: {MIST_AP_ADDRESS}")
print(f"使用するサービス運用用のOMRON BLEアドレス: {OMRON_ADDRESSES}")
print(f"使用するサービス運用用のroom_id: {ROOM_IDS}")

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

# すべてのデータを取得
cursor.execute("SELECT * FROM sensor_data_for_ml ORDER BY timestamp DESC limit 15")

all_rows = cursor.fetchall()
if len(all_rows)<15:
    print("hekko")
print(type(len(all_rows)))