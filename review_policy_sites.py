from pathlib import Path

import pandas as pd

folder = Path(__file__).resolve().parent

# 보충 후보의 실제 대여소 이름과 위치 확인
alternatives = pd.read_csv(
    folder / "tashu_alternatives.csv", encoding="utf-8-sig"
)
stations = pd.read_csv(
    folder / "tashu_yuseong_clean.csv", encoding="utf-8-sig"
)

priority = alternatives.loc[
    alternatives["법정동명"].isin(["반석동", "지족동"])
    & alternatives["대체_대여소_직선거리_m"].gt(500)
].copy()

coordinates = stations[["id", "address", "x_pos", "y_pos"]].rename(
    columns={"id": "0대_대여소_ID", "x_pos": "위도", "y_pos": "경도"}
)
priority = priority.merge(
    coordinates, on="0대_대여소_ID", how="left", validate="one_to_one"
).sort_values("대체_대여소_직선거리_m", ascending=False)

priority.to_csv(
    folder / "tashu_priority_stations.csv", index=False, encoding="utf-8-sig"
)

print("\n[반석동·지족동 보충 우선 검토 지점]")
print(priority[[
    "법정동명", "0대_대여소명", "대체_대여소명",
    "대체_대여소_자전거수", "대체_대여소_직선거리_m",
]].to_string(index=False))

# 위치 현황 파일과 대조해 스냅샷에 빠진 동 확인
location_path = next(folder.glob("*타슈*위치 현황*.csv"), None)
if location_path is None:
    raise FileNotFoundError("asd 폴더에서 타슈 위치 현황 CSV를 찾지 못했습니다.")

try:
    locations = pd.read_csv(location_path, encoding="utf-8-sig")
except UnicodeDecodeError:
    locations = pd.read_csv(location_path, encoding="cp949")

locations.columns = locations.columns.str.strip()

# 인구 자료와 같은 법정동 기준으로 비교하기 위해 주소에서 동을 추출
locations["법정동명"] = locations["주소"].str.extract(
    r"유성구\s+(\S+동)(?=\s|$)"
)
location_counts = locations.groupby("법정동명")["번호"].nunique()

unmatched = pd.read_csv(
    folder / "tashu_station_check_needed.csv", encoding="utf-8-sig"
)
unmatched["6월_위치자료_주소매칭_대여소수"] = (
    unmatched["법정동명"].map(location_counts).fillna(0).astype(int)
)

unmatched[[
    "법정동명", "주간_유동인구", "6월_위치자료_주소매칭_대여소수",
]].to_csv(folder / "tashu_unmatched_review.csv", index=False, encoding="utf-8-sig")

print("\n[스냅샷에 대여소가 없었던 11개 동의 위치 자료 대조]")
print(unmatched[[
    "법정동명", "주간_유동인구", "6월_위치자료_주소매칭_대여소수",
]].to_string(index=False))