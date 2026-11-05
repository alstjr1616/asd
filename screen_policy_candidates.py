from pathlib import Path

import pandas as pd

folder = Path(__file__).resolve().parent
dong = pd.read_csv(folder / "tashu_population_by_dong.csv", encoding="utf-8-sig")
alternatives = pd.read_csv(folder / "tashu_alternatives.csv", encoding="utf-8-sig")

# ① 0대 대여소 중 대체 대여소가 먼 곳을 동별로 집계
distance = "대체_대여소_직선거리_m"
alternatives["대체거리_300m_초과"] = alternatives[distance].gt(300)
alternatives["대체거리_500m_초과"] = alternatives[distance].gt(500)

distance_by_dong = alternatives.groupby("법정동명", as_index=False).agg(
    거리계산_대여소수=(distance, "count"),
    대체거리_300m_초과_수=("대체거리_300m_초과", "sum"),
    대체거리_500m_초과_수=("대체거리_500m_초과", "sum"),
    최대_대체거리_m=(distance, "max"),
)

matched = dong.loc[dong["자료_매칭"].eq("두 자료 모두 있음")].copy()

replenish = matched.loc[matched["자전거_0대_대여소_수"].gt(0)].merge(
    distance_by_dong, on="법정동명", how="left", validate="one_to_one"
)
replenish = replenish.sort_values(
    ["대체거리_500m_초과_수", "자전거_0대_비율_pct"],
    ascending=False,
)
replenish.to_csv(folder / "tashu_replenishment_review.csv",
                 index=False, encoding="utf-8-sig")

# ③ 대여소가 확인된 동에서 유동인구 대비 공급 비교
facility = matched.loc[matched["대여소_수"].gt(0)].copy()
facility["대여소당_주간유동인구_지표"] = (
    facility["주간_유동인구"] / facility["대여소_수"]
).round(1)

# 주간 유동인구가 12개월 모두 있는 동을 같은 조건으로 비교
facility = facility.loc[facility["주간_유효개월수"].eq(12)].sort_values(
    "대여소당_주간유동인구_지표", ascending=False
)
facility.to_csv(folder / "tashu_facility_review.csv",
                index=False, encoding="utf-8-sig")

unmatched = dong.loc[dong["자료_매칭"].eq("유동인구만 있음")].sort_values(
    "주간_유동인구", ascending=False
)
unmatched.to_csv(folder / "tashu_station_check_needed.csv",
                 index=False, encoding="utf-8-sig")

print("\n[① 자전거 보충 검토 후보]")
print(replenish[[
    "법정동명", "출근_유동인구", "자전거_0대_대여소_수",
    "자전거_0대_비율_pct", "거리계산_대여소수",
    "대체거리_300m_초과_수", "대체거리_500m_초과_수",
]].head(10).to_string(index=False))

print("\n[③ 대여·반납소 확충 검토 후보]")
print(facility[[
    "법정동명", "주간_유동인구", "대여소_수",
    "대여소당_주간유동인구_지표",
]].head(10).to_string(index=False))

print("\n[대여소 유무를 별도로 확인할 동]")
print(unmatched[["법정동명", "주간_유동인구"]].to_string(index=False))