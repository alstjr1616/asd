from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "processed"

source = DATA_DIR / "tashu_station_hourly_202610.csv"

df = pd.read_csv(
    source,
    encoding="utf-8-sig",
    dtype={"대여소ID": str},
)
df["날짜"] = pd.to_datetime(df["날짜"])

# 월 경계의 반납 누락 영향을 피하기 위해 10월 1일 제외
dates = pd.date_range("2026-10-02", "2026-10-31", freq="D")
dates = dates[dates.dayofweek < 5]

# 10월 중 이용 기록이 있었던 대여소 전체
stations = sorted(df["대여소ID"].unique())

morning = df[
    df["날짜"].isin(dates)
    & df["시간"].between(7, 8)
].copy()

daily = morning.groupby(
    ["대여소ID", "날짜"]
)[["대여건수", "반납건수"]].sum()

# 기록이 없는 날짜도 포함
# 0은 '파일에서 확인된 이용 기록 없음'이며 운영 여부는 알 수 없음
full_index = pd.MultiIndex.from_product(
    [stations, dates],
    names=["대여소ID", "날짜"],
)

daily = daily.reindex(full_index, fill_value=0).reset_index()
daily["순유출"] = daily["대여건수"] - daily["반납건수"]
daily["순유출발생"] = daily["순유출"] > 0
daily["이용기록있음"] = (
    daily["대여건수"] + daily["반납건수"]
) > 0

summary = daily.groupby("대여소ID").agg(
    분석일수=("날짜", "size"),
    이용기록일수=("이용기록있음", "sum"),
    대여건수_합계=("대여건수", "sum"),
    반납건수_합계=("반납건수", "sum"),
    일평균_대여건수=("대여건수", "mean"),
    일평균_반납건수=("반납건수", "mean"),
    일평균_순유출=("순유출", "mean"),
    순유출_발생일수=("순유출발생", "sum"),
).reset_index()

summary["순유출_발생일비율_pct"] = (
    summary["순유출_발생일수"] / summary["분석일수"] * 100
)

summary = summary.sort_values(
    ["일평균_순유출", "순유출_발생일비율_pct"],
    ascending=[False, False],
)

# 저장과 출력 시 소수 둘째 자리까지 표시
summary = summary.round(2)

daily.to_csv(
    DATA_DIR / "tashu_morning_daily_202610.csv",
    index=False,
    encoding="utf-8-sig",
)
summary.to_csv(
    DATA_DIR / "tashu_morning_summary_202610.csv",
    index=False,
    encoding="utf-8-sig",
)

print("분석 기간: 2026-10-02 ~ 2026-10-31 중 월~금")
print("공휴일 별도 제외 없음")
print("분석 시간: 07:00 이상 ~ 09:00 미만")
print(f"분석 날짜 수: {len(dates)}일")
print(f"분석 대여소 수: {len(stations)}개")

print("\n[일평균 순유출이 큰 대여소 상위 15개]")
print(summary.head(15).to_string(index=False))

print("\n저장 완료")
print("data/processed/tashu_morning_daily_202610.csv")
print("data/processed/tashu_morning_summary_202610.csv")