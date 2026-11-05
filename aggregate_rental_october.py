from pathlib import Path
from collections import Counter
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"

files = [
    path for path in RAW_DIR.rglob("*")
    if path.is_file()
    and path.suffix.lower() == ".csv"
    and "26년10월" in path.name
]

if len(files) != 1:
    raise ValueError(
        f"26년10월 CSV가 정확히 1개 있어야 합니다. 발견: {len(files)}개"
    )

path = files[0]
print("분석 파일:", path.name)

START = pd.Timestamp("2026-10-01")
END = pd.Timestamp("2026-11-01")

columns = [
    "대여일시", "대여_대여소ID", "대여_구",
    "반납일시", "반납_대여소ID", "반납_구",
]

counts = {
    "대여": Counter(),
    "반납": Counter(),
}

stats = Counter()
total_rows = 0

# 파일 전체 대신 10만 행씩 읽기
reader = pd.read_csv(
    path,
    encoding="utf-8-sig",
    usecols=columns,
    dtype=str,
    chunksize=100_000,
)

for number, chunk in enumerate(reader, start=1):
    total_rows += len(chunk)

    # 대여와 반납을 각각의 장소와 시각 기준으로 집계
    for event in ("대여", "반납"):
        district = chunk[f"{event}_구"].str.strip()
        station = chunk[f"{event}_대여소ID"].str.strip()

        timestamp = pd.to_datetime(
            chunk[f"{event}일시"],
            format="%Y-%m-%d %H:%M:%S",
            errors="coerce",
        )

        in_yuseong = district.eq("유성구")
        missing_station = station.fillna("").eq("")
        in_period = timestamp.ge(START) & timestamp.lt(END)

        stats[f"{event}_유성구행"] += int(in_yuseong.sum())
        stats[f"{event}_시각오류"] += int(
            (in_yuseong & timestamp.isna()).sum()
        )
        stats[f"{event}_ID누락"] += int(
            (in_yuseong & missing_station).sum()
        )
        stats[f"{event}_기간밖"] += int(
            (in_yuseong & timestamp.notna() & ~in_period).sum()
        )

        valid = in_yuseong & ~missing_station & in_period

        events = pd.DataFrame({
            "날짜": timestamp.loc[valid].dt.strftime("%Y-%m-%d"),
            "시간": timestamp.loc[valid].dt.hour,
            "대여소ID": station.loc[valid],
        })

        grouped = events.groupby(
            ["날짜", "시간", "대여소ID"]
        ).size()

        counts[event].update(grouped.to_dict())

    print(f"{number}번째 묶음 완료 / 누적 {total_rows:,}행")

keys = sorted(set(counts["대여"]) | set(counts["반납"]))

if not keys:
    raise ValueError("집계 결과가 없습니다. 지역명과 날짜를 확인해주세요.")

rows = []

for date, hour, station_id in keys:
    key = (date, hour, station_id)
    rentals = counts["대여"][key]
    returns = counts["반납"][key]

    rows.append({
        "날짜": date,
        "시간": hour,
        "대여소ID": station_id,
        "대여건수": rentals,
        "반납건수": returns,
        "순유출": rentals - returns,
    })

result = pd.DataFrame(rows)

OUT_DIR.mkdir(parents=True, exist_ok=True)
output = OUT_DIR / "tashu_station_hourly_202610.csv"
result.to_csv(output, index=False, encoding="utf-8-sig")

print("\n[집계 결과]")
print(f"읽은 원본 행: {total_rows:,}")
print(f"집계된 유성구 대여: {result['대여건수'].sum():,}건")
print(f"집계된 유성구 반납: {result['반납건수'].sum():,}건")
print(f"이용 기록이 있는 대여소: {result['대여소ID'].nunique():,}개")
print(f"결과 행: {len(result):,}")

print("\n[자료 확인]")
for key, value in stats.items():
    print(f"{key}: {value:,}")

print("\n[처음 10행]")
print(result.head(10).to_string(index=False))
print("\n저장 완료:", output)