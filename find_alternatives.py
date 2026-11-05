from pathlib import Path

import numpy as np
import pandas as pd

folder = Path(__file__).resolve().parent

yuseong = pd.read_csv(folder / "tashu_yuseong_clean.csv", encoding="utf-8-sig")
all_stations = pd.read_csv(
    folder / "tashu_station_20261105_0930.csv",
    encoding="utf-8-sig",
)

empty = yuseong.loc[yuseong["parking_count"].eq(0)].copy()
available = all_stations.loc[all_stations["parking_count"].gt(0)].copy()

# 이 파일에서 x_pos는 위도, y_pos는 경도
for stations in (empty, available):
    for column in ("x_pos", "y_pos"):
        stations[column] = pd.to_numeric(stations[column], errors="coerce")

empty = empty.dropna(subset=["x_pos", "y_pos"])
available = available.dropna(subset=["x_pos", "y_pos"])

if available.empty:
    raise ValueError("비교할 수 있는 대체 대여소가 없습니다.")

# 위도·경도를 이용해 지표면 기준 직선거리 계산
lat2 = np.radians(available["x_pos"].to_numpy())
lon2 = np.radians(available["y_pos"].to_numpy())

results = []

for station in empty.itertuples(index=False):
    lat1 = np.radians(station.x_pos)
    lon1 = np.radians(station.y_pos)

    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    distance_m = 2 * 6_371_000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    nearest_index = distance_m.argmin()
    nearest = available.iloc[nearest_index]

    results.append({
        "법정동명": station.법정동명,
        "0대_대여소_ID": station.id,
        "0대_대여소명": station.name,
        "대체_대여소_ID": nearest["id"],
        "대체_대여소명": nearest["name"],
        "대체_대여소_자전거수": nearest["parking_count"],
        "대체_대여소_직선거리_m": round(distance_m[nearest_index], 1),
    })

result = pd.DataFrame(results).sort_values(
    "대체_대여소_직선거리_m", ascending=False
)
result.to_csv(folder / "tashu_alternatives.csv", index=False, encoding="utf-8-sig")

print("거리 계산을 완료한 0대 대여소 수:", len(result))
print(result.head(10).to_string(index=False))
print("저장 완료: tashu_alternatives.csv")