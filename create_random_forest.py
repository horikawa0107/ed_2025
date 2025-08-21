import pandas as pd
import mysql.connector
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib

# 1. MySQL接続関数
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',       # 環境に応じて変更（例: 'db' など）
        user='root',
        password='password',
        database='flask_db'
    )

# 2. MySQLからデータを読み込み（前処理済みテーブル）
def load_data_from_mysql():
    conn = get_db_connection()
    query = """
        SELECT avg_temperature , avg_humidity, avg_light, avg_pressure,  avg_sound_level , avg_discomfort_index, avg_month 
        FROM sensor_data_avg;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --- データ取得 ---
df = load_data_from_mysql()
print(df)

# --- 特徴量と目的変数に分割 ---
features = ['avg_temperature', 'avg_humidity', 'avg_light', 'avg_pressure', 'avg_sound_level', 'avg_month']
X = df[features]
y = df['avg_discomfort_index']

# --- 学習用・テスト用データに分割 ---
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print(type(X_test))
print(f'X_test:\n{X_test}')

# --- モデル構築と学習 ---
model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
model.fit(X_train, y_train)

# --- 予測と評価 ---
y_pred = model.predict(X_test)
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"\n平均二乗誤差 (MSE): {mse:.2f}")
print(f"決定係数 (R^2): {r2:.2f}")

# --- モデル保存 ---
joblib.dump(model, "/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/models/comfort_score_rf_model.pkl")

# --- 特徴量の重要度確認 ---
importances = pd.Series(model.feature_importances_, index=features).sort_values(ascending=False)
print("\n特徴量の重要度:")
print(importances)

# --- 保存済みモデルでのテスト予測 ---
model_pkl = joblib.load(open('/Users/horikawafuka2/Documents/class_2025/ed/dev_mysql/models/comfort_score_rf_model.pkl', 'rb'))
y_loaded_model = model_pkl.predict(X_test)
print(f'\nモデルのテスト出力:\n{y_loaded_model}')