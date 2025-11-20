# test_sample.py
import pytest
import numpy as np
import pandas as pd
from page import predict_comfort_score

# 正常データ（ce_001）

print(f"pandas:{pd.__version__}")
print(f"numpy:{np.__version__}")

normal_input = {
    "avg_temperature": 25.0,
    "avg_humidity": 50.0,
    "avg_light": 300.0,
    "avg_pressure": 1013.0,
    "avg_sound_level": 40.0,
    "month": 5
}

# 最小/最大値（ce_002）
min_max_input = {
    "avg_temperature": 0.0,     # 温度 min
    "avg_humidity": 100.0,      # 湿度 max
    "avg_light": 0.0,
    "avg_pressure": 900.0,
    "avg_sound_level": 0.0,
    "month": 12
}

# 欠損値あり（ce_003）
missing_input = {
    "avg_temperature": 26.0,
    "avg_humidity": None,       # ← 欠損
    "avg_light": 350.0,
    "avg_pressure": 1010.0,
    "avg_sound_level": None,    # ← 欠損
    "month": 7
}

# -------------------------------
# ce_001 : 正常データの推定
# -------------------------------
def test_ce001_normal_input():
    result1 = predict_comfort_score(normal_input)
    result2 = predict_comfort_score(normal_input)

    # 0〜100 の範囲
    assert 0 <= result1 <= 100, "正常入力の結果が0〜100にありません"

    # 再現性
    assert result1 == result2, "同じ入力で異なる結果が返されています"


# -------------------------------
# ce_002 : 最小・最大値の検証
# -------------------------------
def test_ce002_min_max_input():
    result = predict_comfort_score(min_max_input)
    assert result is not None, "結果がNoneになっています"
    assert 0 <= result <= 100, "最小/最大値入力の結果が0〜100にありません"


# -------------------------------
# ce_003 : 欠損値の扱い
# -------------------------------
def test_ce003_missing_values():
    # 欠損値を np.nan に置き換える（XGBoost が None を処理できないため）
    fixed_input = {
        k: (np.nan if v is None else v)
        for k, v in missing_input.items()
    }

    result = predict_comfort_score(fixed_input)

    # クラッシュしない
    assert result is not None, "欠損値でNoneが返されています"

    # 範囲チェック
    assert 0 <= result <= 100, "欠損値入力の結果が0〜100にありません"
# import pandas
# import numpy 
