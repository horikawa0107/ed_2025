import pandas as pd
import pytest
from unittest.mock import MagicMock
from dev_mysql.page import train_and_save_model, MODEL_PATH
# -----------------------------------------------------
# 正常系：必要な列がすべて揃っている場合
# -----------------------------------------------------
def test_train_model_schema_ok(tmp_path, monkeypatch):
    # モデル保存先をテスト用ディレクトリに変更
    monkeypatch.setattr("page.MODEL_PATH", tmp_path / "test_model.json")

    # テスト用 DataFrame（正しいスキーマ）
    df = pd.DataFrame({
        "avg_temperature": [20, 21, 22, 23, 24],
        "avg_humidity": [50, 51, 52, 53, 54],
        "avg_light": [100, 110, 120, 130, 140],
        "avg_pressure": [1010, 1011, 1012, 1013, 1014],
        "avg_sound_level": [30, 35, 40, 45, 50],
        "month": [1, 1, 1, 1, 1],
        "score_from_avg_device_count": [3, 4, 5, 6, 7]
    })

    mock_loader = MagicMock(return_value=df)

    # 実行（返り値無しなので例外が出ないことが「成功」）
    train_and_save_model(load_data_func=mock_loader)

    # モデルファイルがちゃんと保存されているか
    assert (tmp_path / "test_model.json").exists()


# -----------------------------------------------------
# 異常系：列が足りない場合
# -----------------------------------------------------
def test_train_model_schema_missing_columns():
    df_missing = pd.DataFrame({
        "avg_temperature": [20, 21, 22],
        # 敢えて "avg_humidity" がない
        "avg_light": [100, 110, 120],
        "avg_pressure": [1010, 1011, 1012],
        "avg_sound_level": [30, 40, 50],
        "month": [1, 1, 1],
        "score_from_avg_device_count": [3, 4, 5]
    })

    mock_loader = MagicMock(return_value=df_missing)

    with pytest.raises(KeyError):
        train_and_save_model(load_data_func=mock_loader)


# -----------------------------------------------------
# 異常系：データが少なくて学習スキップ
# -----------------------------------------------------
def test_train_model_not_enough_data(capfd):
    df_small = pd.DataFrame({
        "avg_temperature": [20],
        "avg_humidity": [50],
        "avg_light": [100],
        "avg_pressure": [1010],
        "avg_sound_level": [30],
        "month": [1],
        "score_from_avg_device_count": [3]
    })

    mock_loader = MagicMock(return_value=df_small)

    train_and_save_model(load_data_func=mock_loader)

    out, _ = capfd.readouterr()
    assert "データが足りません" in out