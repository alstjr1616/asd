from pathlib import Path
from zipfile import ZipFile

import pandas as pd

folder = Path(__file__).resolve().parent
zip_path = next(
    folder.glob("*법정동별*유동인구*.zip"),
    None,
)

if zip_path is None:
    raise FileNotFoundError("asd 폴더에서 법정동별 유동인구 ZIP을 찾지 못했습니다.")

with ZipFile(zip_path) as archive:
    files = archive.namelist()
    print("ZIP 안의 파일 목록")
    for name in files:
        print(name)

    csv_files = [name for name in files if name.lower().endswith(".csv")]

    if csv_files:
        sample_file = csv_files[0]

        for encoding in ("utf-8-sig", "cp949"):
            try:
                with archive.open(sample_file) as file:
                    sample = pd.read_csv(file, encoding=encoding, nrows=5)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("CSV의 한글 인코딩을 확인해야 합니다.")

        print("\n확인한 파일", sample_file)
        print("컬럼 목록", sample.columns.tolist())
        print("\n처음 5행")
        print(sample.to_string(index=False))
    else:
        print("\nZIP 안에 CSV가 없습니다. 위 목록에서 파일 형식을 확인해주세요.")