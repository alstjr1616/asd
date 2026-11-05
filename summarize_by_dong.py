from pathlib import Path

import pandas as pd

folder = Path(__file__).resolve().parent
df = pd.read_csv(folder / "tashu_yuseong_clean.csv", encoding="utf-8-sig")

print("중복 대여소 ID 행 수:", df["id"].duplicated().sum())
print("자전거 수량이 비어 있는 행:", df["parking_count"].isna().sum())

df["자전거_0대"] = df["parking_count"].eq(0)

summary = df.groupby("법정동명", as_index=False).agg(
    대여소_수=("id", "nunique"),
    수량_확인_행수=("parking_count", "count"),
    대여가능_자전거_수=("parking_count", lambda s: s.sum(min_count=1)),
    자전거_0대_대여소_수=("자전거_0대", "sum"),
)

summary["자전거_0대_비율_pct"] = (
    summary["자전거_0대_대여소_수"]
    .div(summary["수량_확인_행수"].replace(0, float("nan")))
    .mul(100)
    .round(1)
)

summary = summary.sort_values("자전거_0대_대여소_수", ascending=False)
summary.to_csv(folder / "tashu_by_dong.csv", index=False, encoding="utf-8-sig")

print(summary.head(10).to_string(index=False))
print("저장 완료: tashu_by_dong.csv")