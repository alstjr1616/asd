from pathlib import Path
import re
from zipfile import ZipFile

import pandas as pd

folder = Path(__file__).resolve().parent
zip_path = next(folder.glob("*법정동별*유동인구*.zip"), None)

if zip_path is None:
    raise FileNotFoundError("asd 폴더에 유동인구 ZIP 파일이 필요합니다.")

# ZIP에서 2022년 월별 CSV만 읽기
monthly = []

with ZipFile(zip_path) as archive:
    for name in sorted(archive.namelist()):
        if not re.search(r"2022(?:0[1-9]|1[0-2])\.csv$", name, re.IGNORECASE):
            continue

        for encoding in ("utf-8-sig", "cp949"):
            try:
                with archive.open(name) as file:
                    monthly.append(pd.read_csv(file, encoding=encoding))
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(f"CSV 인코딩을 확인해주세요. {name}")

if len(monthly) != 12:
    raise ValueError(f"2022년 월별 파일이 12개여야 합니다. 확인된 파일은 {len(monthly)}개입니다.")

population = pd.concat(monthly, ignore_index=True)
population.columns = population.columns.str.strip()
population["법정동명"] = population["법정동명"].str.strip()
population["시간대"] = population["시간대"].str.strip()

population["일평균유동인구"] = pd.to_numeric(
    population["일평균유동인구"].astype("string").str.replace(",", "", regex=False),
    errors="coerce",
)

selected = population.loc[population["시간대"].isin(["출근", "주간"])].copy()

# 동·월·시간대가 같은 행이 여러 개면 집계 전에 확인
keys = ["법정동명", "기준월", "시간대"]
duplicates = selected.loc[selected.duplicated(keys, keep=False)]

if not duplicates.empty:
    print(duplicates.head(10).to_string(index=False))
    raise ValueError("동·월·시간대가 같은 행이 여러 개 있습니다.")

# 시간대별로 12개월의 일평균유동인구 값 평균
by_time = selected.groupby(["법정동명", "시간대"])["일평균유동인구"]
means = by_time.mean().unstack().reindex(columns=["출근", "주간"])
counts = by_time.count().unstack().reindex(columns=["출근", "주간"])

means.columns = ["출근_유동인구", "주간_유동인구"]
counts.columns = ["출근_유효개월수", "주간_유효개월수"]
population_by_dong = means.round(1).join(counts).reset_index()

tashu = pd.read_csv(folder / "tashu_by_dong.csv", encoding="utf-8-sig")
tashu["법정동명"] = tashu["법정동명"].str.strip()

# 유동인구에만 있는 동과 타슈 집계에만 있는 동을 모두 남기기
result = population_by_dong.merge(
    tashu, on="법정동명", how="outer", validate="one_to_one", indicator=True
)

result["자료_매칭"] = result.pop("_merge").map({
    "both": "두 자료 모두 있음",
    "left_only": "유동인구만 있음",
    "right_only": "타슈 집계만 있음",
})

result = result.sort_values("주간_유동인구", ascending=False)
result.to_csv(folder / "tashu_population_by_dong.csv", index=False, encoding="utf-8-sig")

print("2022년 월별 파일 수", len(monthly))
print("\n동별 자료 매칭 결과")
print(result["자료_매칭"].value_counts().to_string())

print("\n주간 유동인구 상위 10개 동")
columns = ["법정동명", "출근_유동인구", "주간_유동인구",
           "대여소_수", "자전거_0대_비율_pct", "자료_매칭"]
print(result[columns].head(10).to_string(index=False))

print("\n한쪽 자료에만 있는 동")
print(result.loc[result["자료_매칭"].ne("두 자료 모두 있음"),
                 ["법정동명", "자료_매칭"]].to_string(index=False))

print("\n저장 완료 - tashu_population_by_dong.csv")