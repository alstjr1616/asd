from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"

files = [
    p for p in RAW_DIR.rglob("*")
    if p.is_file()
    and p.suffix.lower() == ".csv"
    and "26년10월" in p.name
]

if len(files) != 1:
    raise ValueError(f"10월 CSV가 1개여야 합니다. 발견: {len(files)}개")

summary = pd.read_csv(
    OUT_DIR / "tashu_morning_summary_202610.csv",
    encoding="utf-8-sig",
    dtype={"대여소ID": str},
)

columns = []
for event in ("대여", "반납"):
    columns += [
        f"{event}일시",
        f"{event}_대여소ID",
        f"{event}_대여소명",
        f"{event}_구",
        f"{event}_동",
        f"{event}_X좌표",
        f"{event}_Y좌표",
    ]

info_columns = [
    "대여소ID", "대여소명", "구", "동", "위도", "경도"
]
parts = []

reader = pd.read_csv(
    files[0],
    encoding="utf-8-sig",
    usecols=columns,
    dtype=str,
    chunksize=100_000,
)

for number, chunk in enumerate(reader, start=1):
    for event in ("대여", "반납"):
        rename = {
            f"{event}일시": "관측시각",
            f"{event}_대여소ID": "대여소ID",
            f"{event}_대여소명": "대여소명",
            f"{event}_구": "구",
            f"{event}_동": "동",
            f"{event}_X좌표": "위도",
            f"{event}_Y좌표": "경도",
        }

        info = chunk[list(rename)].rename(columns=rename).copy()

        for col in ["대여소ID", "대여소명", "구", "동"]:
            info[col] = info[col].str.strip()

        info["관측시각"] = pd.to_datetime(
            info["관측시각"],
            format="%Y-%m-%d %H:%M:%S",
            errors="coerce",
        )

        for col in ["위도", "경도"]:
            info[col] = pd.to_numeric(info[col], errors="coerce")

        valid = (
            info["구"].eq("유성구")
            & info["대여소ID"].fillna("").ne("")
            & info["관측시각"].ge("2026-10-01")
            & info["관측시각"].lt("2026-11-01")
        )
        info = info.loc[valid]

        # 同じ情報については最も新しい観測だけを残す
        info = (
            info.sort_values("관측시각")
            .drop_duplicates(info_columns, keep="last")
        )
        parts.append(info)

    print(f"{number}번째 묶음 확인 완료")

all_info = pd.concat(parts, ignore_index=True)

versions = (
    all_info.drop_duplicates(info_columns)
    .groupby("대여소ID")
    .size()
    .rename("정보버전수")
    .reset_index()
)

latest = (
    all_info.sort_values("관측시각")
    .drop_duplicates("대여소ID", keep="last")
    .merge(versions, on="대여소ID", validate="one_to_one")
)

result = summary.merge(
    latest,
    on="대여소ID",
    how="left",
    validate="one_to_one",
    indicator=True,
)

print("\n[대여소 정보 연결 결과]")
print(result["_merge"].value_counts().to_string())

result["정보매칭"] = result.pop("_merge").eq("both")
result["좌표확인필요"] = ~(
    result["위도"].between(33, 39)
    & result["경도"].between(124, 132)
)

result = result.sort_values("일평균_순유출", ascending=False)

output = OUT_DIR / "tashu_morning_summary_named_202610.csv"
result.to_csv(output, index=False, encoding="utf-8-sig")

print("\n[아침 순유출 상위 15개 대여소]")
show_columns = [
    "대여소ID", "대여소명", "동",
    "일평균_대여건수", "일평균_반납건수",
    "일평균_순유출", "순유출_발생일비율_pct",
    "정보버전수",
]
print(result[show_columns].head(15).to_string(index=False))

print("\n정보가 여러 버전인 대여소 수:",
      int(result["정보버전수"].gt(1).sum()))
print("좌표 확인이 필요한 대여소 수:",
      int(result["좌표확인필요"].sum()))
print("\n저장 완료:", output)