from pathlib import Path

import pandas as pd

folder = Path(__file__).resolve().parent
source = folder / "tashu_station_20261105_0930.csv"
df = pd.read_csv(source, encoding="utf-8-sig")

is_yuseong = df["address"].str.contains(r"^대전광역시\s+유성구\s+", na=False)
ys = df.loc[is_yuseong, ["id", "name", "address", "x_pos", "y_pos", "parking_count"]].copy()

ys["법정동명"] = ys["address"].str.extract(r"유성구\s+(\S+동)(?=\s|$)")
ys["parking_count"] = pd.to_numeric(ys["parking_count"], errors="coerce")

print("전체 행:", len(df))
print("유성구 행:", len(ys))
print("자전거 0대 행:", ys["parking_count"].eq(0).sum())
print("법정동을 못 찾은 행:", ys["법정동명"].isna().sum())

output = folder / "tashu_yuseong_clean.csv"
ys.to_csv(output, index=False, encoding="utf-8-sig")
print("저장 완료:", output.name)