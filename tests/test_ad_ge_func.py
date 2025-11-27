import pytest
from page import generate_advice   # ← generate_advice を定義しているファイル名に合わせて変更してください

# 共通テンプレート
def base_data(**kwargs):
    data = {
        "month": 6,
        "temperature": 25,
        "humidity": 50,
        "pressure": 1010,
        "sound_level": 40,
        "light": 600,
    }
    data.update(kwargs)
    return data

# --- ad_001 夏：高温 ---
def test_ad_001_summer_hot():
    data = base_data(month=7, temperature=30)
    assert "室温が高く熱中症のリスクがあります。冷房を利用しましょう。" in generate_advice(data)

# --- ad_002 夏：涼しい ---
def test_ad_002_summer_cool():
    data = base_data(month=8, temperature=26)
    assert "やや涼しめの快適な室温です。" in generate_advice(data)

# --- ad_003 冬：低温 ---
def test_ad_003_winter_cold():
    data = base_data(month=1, temperature=18)
    assert "室温が低く寒く感じる可能性があります。暖房を使用してください。" in generate_advice(data)

# --- ad_004 冬：高温 ---
def test_ad_004_winter_hot():
    data = base_data(month=12, temperature=27)
    assert "室温がやや高めです。暖房の調整を検討しましょう。" in generate_advice(data)

# --- ad_005 春：低温 ---
def test_ad_005_spring_low():
    data = base_data(month=4, temperature=19)
    assert "少し肌寒いかもしれません。" in generate_advice(data)

# --- ad_006 秋：高温 ---
def test_ad_006_autumn_hot():
    data = base_data(month=10, temperature=28)
    assert "暑く感じるかもしれません。冷房の使用を検討してください。" in generate_advice(data)

# --- ad_007 騒音 ---
def test_ad_007_noise():
    data = base_data(sound_level=75)
    assert "騒音レベルが高く、集中しにくい環境です。静かな場所への移動をおすすめします。" in generate_advice(data)

# --- ad_008 低気圧 ---
def test_ad_008_low_pressure():
    data = base_data(pressure=1000)
    assert "気圧が低く、頭痛やだるさを感じる人がいるかもしれません。" in generate_advice(data)

# --- ad_009 夏：高湿度 ---
def test_ad_009_summer_high_humidity():
    data = base_data(month=8, humidity=75)
    assert "湿度が高く蒸し暑く感じるかもしれません。除湿器や冷房を使用してください。" in generate_advice(data)

# --- ad_010 冬：低湿度 ---
def test_ad_010_winter_low_humidity():
    data = base_data(month=1, humidity=30)
    assert "湿度が低く乾燥しています。加湿器を使いましょう。" in generate_advice(data)

# --- ad_011 複数条件一致 ---
def test_ad_011_multiple():
    data = base_data(
        month=8, temperature=32, humidity=80, sound_level=72, pressure=980, light=400
    )
    result = generate_advice(data)
    assert "熱中症" in result
    assert "湿度が高く蒸し暑く" in result
    assert "騒音レベルが高く" in result
    assert "気圧が低く" in result
    assert "暗くて見えにくい環境" in result

# --- ad_012 季節判定 ---
def test_ad_012_season_boundary():
    # 5月 → 春
    assert "少し肌寒い" in generate_advice(base_data(month=5, temperature=18))
    # 6月 → 夏
    assert "涼しめ" in generate_advice(base_data(month=6, temperature=25))
    # 9月 → 秋
    assert "暑く感じる" in generate_advice(base_data(month=9, temperature=28))
    # 12月 → 冬
    assert "寒く感じる" in generate_advice(base_data(month=12, temperature=17))

# --- ad_013 照度：低 ---
def test_ad_013_low_light():
    data = base_data(light=400)
    assert "暗くて見えにくい環境です。部屋の照明をつけたり、窓を開けましょう。" in generate_advice(data)

# --- ad_014 照度：高 ---
def test_ad_014_high_light():
    data = base_data(light=800)
    assert "少し眩しい環境です。窓を閉めたり、ライトを弱くした方がいいかもしれません。" in generate_advice(data)

# --- ad_015 特になし ---
def test_ad_015_no_condition():
    data = base_data(
        month=5, temperature=22, humidity=50, pressure=1020, sound_level=30, light=600
    )
    assert generate_advice(data) == "特になし"
