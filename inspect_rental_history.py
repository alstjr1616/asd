from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"

files = sorted(
    path for path in RAW_DIR.rglob("*")
    if path.is_file() and path.suffix.lower() == ".csv"
)

print(f"발견한 CSV 파일 수: {len(files)}")

if not files:
    print("data/raw 안에 CSV 파일이 있는지 확인해주세요.")
    print("ZIP 파일이라면 먼저 압축을 풀어주세요.")
    raise SystemExit

column_sets = {}

for path in files:
    print("\n" + "=" * 60)
    print("파일:", path.relative_to(RAW_DIR))
    print(f"용량: {path.stat().st_size / (1024 ** 2):.1f} MB")

    sample = None

    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            sample = pd.read_csv(
                path,
                encoding=encoding,
                nrows=5,
                dtype=str,
            )
            print("읽기에 성공한 인코딩:", encoding)
            break
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            print("빈 파일입니다.")
            break
        except pd.errors.ParserError as error:
            print("CSV 구조 확인이 필요합니다:", error)
            break

    if sample is None:
        print("파일을 읽지 못했습니다. 위 내용을 확인해주세요.")
        continue

    print("컬럼 목록:", sample.columns.tolist())

    columns = tuple(sample.columns)
    column_sets.setdefault(columns, []).append(path.name)

    # 동일한 컬럼 구조는 첫 번째 파일에서만 샘플 출력
    if len(column_sets[columns]) == 1:
        print("\n처음 5행")
        print(sample.to_string(index=False))

print("\n" + "=" * 60)
print("컬럼 구조 비교")

for number, (columns, names) in enumerate(column_sets.items(), start=1):
    print(f"\n구조 {number}: {len(names)}개 파일")
    print("컬럼:", list(columns))