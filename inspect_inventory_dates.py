from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent

# 기존에 확보한 타슈 현황 원본만 확인
files = sorted({
    *ROOT.glob("tashu_station_*.csv"),
    *ROOT.glob("*타슈정보*.csv"),
    *ROOT.glob("*공공자전거*위치*.csv"),
})

if not files:
    print("확인할 현황 파일을 찾지 못했습니다.")
    print("이 코드를 원본 CSV가 있는 asd 폴더에 저장했는지 확인해주세요.")
    raise SystemExit

time_words = (
    "일시", "일자", "날짜", "시간", "기준",
    "수집", "갱신", "수정", "생성", "업데이트",
    "date", "time", "updated", "created",
)

for path in files:
    print("\n" + "=" * 60)
    print("파일:", path.name)
    print(f"파일 크기: {path.stat().st_size / 1024 / 1024:.2f} MB")

    encoding_found = None

    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            sample = pd.read_csv(
                path,
                encoding=encoding,
                dtype=str,
                nrows=5,
            )
            encoding_found = encoding
            break
        except UnicodeDecodeError:
            continue

    if encoding_found is None:
        print("인코딩을 확인하지 못했습니다.")
        continue

    print("인코딩:", encoding_found)
    print("전체 열 이름:", sample.columns.tolist())

    time_columns = [
        column
        for column in sample.columns
        if any(word in str(column).lower() for word in time_words)
    ]

    print("\n처음 3행:")
    print(sample.head(3).to_string(index=False))

    if not time_columns:
        print("\n날짜·시간 관련 열을 찾지 못했습니다.")
        print("파일명이나 다운로드 날짜를 실제 관측일로 사용할 수는 없습니다.")
        continue

    print("\n날짜·시간 관련 열:", time_columns)

    row_count = 0
    missing = {column: 0 for column in time_columns}
    frequencies = {column: {} for column in time_columns}

    try:
        for chunk in pd.read_csv(
            path,
            encoding=encoding_found,
            dtype=str,
            usecols=time_columns,
            chunksize=100_000,
        ):
            row_count += len(chunk)

            for column in time_columns:
                values = chunk[column].astype("string").str.strip()
                values = values.replace("", pd.NA)

                missing[column] += int(values.isna().sum())

                for value, count in values.dropna().value_counts().items():
                    frequencies[column][value] = (
                        frequencies[column].get(value, 0) + int(count)
                    )

    except UnicodeDecodeError:
        print("파일 뒷부분에서 인코딩 오류가 발생했습니다.")
        print("위의 열 이름과 처음 3행 결과를 보내주세요.")
        continue

    print(f"\n전체 행 수: {row_count:,}")

    for column in time_columns:
        counts = frequencies[column]

        print(f"\n[{column}]")
        print(f"비어 있는 행: {missing[column]:,}")
        print(f"서로 다른 값의 수: {len(counts):,}")
        print("자주 등장하는 값 최대 10개:")

        for value, count in sorted(
            counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]:
            print(f"  {value}: {count:,}행")

print("\n확인 완료")
print("주의: 데이터기준일·시설등록일이 자전거 수량 관측 시각인지는")
print("열의 의미를 확인한 후 판단해야 합니다.")