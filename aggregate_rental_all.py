"""11개월 원본을 묶어 집계합니다. 원본과 기존 10월 결과는 변경하지 않습니다."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import re
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'data' / 'processed'
START = pd.Timestamp('2025-12-01')
END = pd.Timestamp('2026-11-01')  # 미포함
EXPECTED = set(pd.period_range('2025-12', '2026-10', freq='M').astype(str))
REQUIRED = ['자전거번호', '대여일시', '반납일시'] + [
    f'{side}_{col}' for side in ['대여', '반납']
    for col in ['대여소ID', '대여소명', 'X좌표', 'Y좌표', '구', '동']
]


def source_month(path):
    match = re.search(r'(\d{2,4})년\s*(\d{1,2})월', path.name)
    if not match:
        return None
    y, m = map(int, match.groups())
    return f'{y + 2000 if y < 100 else y:04d}-{m:02d}'


def encoding_for(path):
    # 파일 끝까지 읽어 인코딩을 확인한 뒤 집계하여 재시도로 인한 이중 집계를 방지
    for enc in ('utf-8-sig', 'cp949', 'euc-kr'):
        try:
            with path.open(encoding=enc) as f:
                while f.read(1024 * 1024):
                    pass
            return enc
        except UnicodeDecodeError:
            pass
    raise ValueError(f'인코딩 확인 실패: {path.name}')


def run():
    files = sorted(p for p in RAW.rglob('*.csv')
                   if '대여이력' in p.name and source_month(p) in EXPECTED)
    groups = {}
    for p in files:
        groups.setdefault(source_month(p), []).append(p)
    if set(groups) != EXPECTED or any(len(v) != 1 for v in groups.values()):
        raise ValueError('월별 원본이 정확히 1개씩 필요합니다. 누락 월: '
                         + str(sorted(EXPECTED - set(groups)))
                         + '\n중복 월: ' + str({k: [p.name for p in v] for k, v in groups.items() if len(v) > 1}))
    OUT.mkdir(parents=True, exist_ok=True)
    dbpath = OUT / '_tashu_all_build.sqlite'
    dbpath.unlink(missing_ok=True)
    con = sqlite3.connect(dbpath)
    con.executescript('''
      CREATE TABLE seen(k TEXT PRIMARY KEY) WITHOUT ROWID;
      CREATE TEMP TABLE incoming(k TEXT PRIMARY KEY) WITHOUT ROWID;
      CREATE TABLE counts(day TEXT, hour INTEGER, station TEXT, rent INTEGER, ret INTEGER,
                          PRIMARY KEY(day,hour,station)) WITHOUT ROWID;
    ''')
    stats = Counter()
    reports = []
    stations = {}
    versions = {}
    rent_days = set()
    fingerprints = set()
    upsert = '''INSERT INTO counts VALUES(?,?,?,?,?) ON CONFLICT(day,hour,station)
                 DO UPDATE SET rent=rent+excluded.rent, ret=ret+excluded.ret'''
    try:
        for month in sorted(groups):
            path = groups[month][0]
            enc = encoding_for(path)
            digest = hashlib.sha256()
            with path.open('rb') as f:
                for part in iter(lambda: f.read(1024 * 1024), b''):
                    digest.update(part)
            sha = digest.hexdigest()
            if sha in fingerprints:
                raise ValueError('내용이 동일한 파일: ' + path.name)
            fingerprints.add(sha)
            report = {'파일': path.name, '파일월': month, '인코딩': enc,
                      'SHA256': sha, '원본행': 0, '중복제외': 0}
            print(f'\n분석: {path.name} ({enc})', flush=True)
            for batch, raw in enumerate(pd.read_csv(path, encoding=enc, dtype=str,
                                                     chunksize=100_000), 1):
                missing = set(REQUIRED) - set(raw.columns)
                if missing:
                    raise ValueError(f'{path.name}: 필요한 열 누락 {missing}')
                report['원본행'] += len(raw)
                stats['원본행'] += len(raw)
                # 전체 열 값이 같은 중복만 제외. 자전거 번호는 집계 결과에 저장하지 않음.
                normalized = raw.fillna('').reindex(sorted(raw.columns), axis=1)
                h1 = pd.util.hash_pandas_object(normalized, index=False, hash_key='tashu2026key0001')
                h2 = pd.util.hash_pandas_object(normalized, index=False, hash_key='tashu2026key0002')
                keys = pd.Series([f'{a:016x}{b:016x}' for a, b in zip(h1, h2)], index=raw.index)
                unique = ~keys.duplicated()
                con.execute('DELETE FROM incoming')
                con.executemany('INSERT INTO incoming VALUES(?)', ((k,) for k in keys[unique]))
                new = {r[0] for r in con.execute('SELECT k FROM incoming WHERE NOT EXISTS (SELECT 1 FROM seen WHERE seen.k=incoming.k)')}
                keep = unique & keys.isin(new)
                dropped = int((~keep).sum())
                report['중복제외'] += dropped
                stats['완전동일행_중복제외'] += dropped
                con.execute('INSERT OR IGNORE INTO seen SELECT k FROM incoming')
                frame = raw.loc[keep].copy()
                rental_time = pd.to_datetime(frame['대여일시'], errors='coerce')
                return_time = pd.to_datetime(frame['반납일시'], errors='coerce')
                stats['전체_대여시각오류'] += int(rental_time.isna().sum())
                stats['전체_반납시각오류'] += int(return_time.isna().sum())
                stats['반납이_대여보다_빠른행'] += int((return_time < rental_time).sum())
                stats['파일월과_대여월_불일치'] += int((rental_time.notna() & rental_time.dt.strftime('%Y-%m').ne(month)).sum())
                rent_days.update(rental_time[(rental_time >= START) & (rental_time < END)].dt.strftime('%Y-%m-%d'))
                for side, times in [('대여', rental_time), ('반납', return_time)]:
                    mask = frame[f'{side}_구'].fillna('').str.strip().eq('유성구')
                    ids = frame[f'{side}_대여소ID'].fillna('').str.strip()
                    stats[f'{side}_유성구시각오류'] += int((mask & times.isna()).sum())
                    stats[f'{side}_유성구ID누락'] += int((mask & ids.eq('')).sum())
                    within = times.ge(START) & times.lt(END)
                    stats[f'{side}_유성구기간밖'] += int((mask & times.notna() & ~within).sum())
                    mask &= times.notna() & ids.ne('') & within & ~(return_time < rental_time)
                    events = pd.DataFrame({
                        '날짜': times[mask].dt.strftime('%Y-%m-%d'),
                        '시간': times[mask].dt.hour,
                        '대여소ID': ids[mask],
                    })
                    stats[f'{side}_집계'] += len(events)
                    counts = events.groupby(['날짜', '시간', '대여소ID']).size()
                    con.executemany(upsert, ((d, int(h), sid, int(n) if side == '대여' else 0,
                                             int(n) if side == '반납' else 0)
                                            for (d, h, sid), n in counts.items()))
                    meta = frame.loc[mask, [f'{side}_{c}' for c in ['대여소명','동','X좌표','Y좌표']]].copy()
                    meta.columns = ['대여소명','동','위도','경도']
                    meta['대여소ID'] = ids[mask]
                    meta['시각'] = times[mask]
                    for sid, grp in meta.groupby('대여소ID'):
                        first, last = grp['시각'].min(), grp['시각'].max()
                        row = grp.sort_values('시각').iloc[-1]
                        if sid not in stations:
                            stations[sid] = {'대여소ID': sid, '최초기록일': first, '최종기록일': last}
                            versions[sid] = set()
                        entry = stations[sid]
                        entry['최초기록일'] = min(first, entry['최초기록일'])
                        if last >= entry['최종기록일']:
                            entry.update({c: row[c] for c in ['대여소명','동','위도','경도']})
                            entry['최종기록일'] = last
                        versions[sid].update(tuple('' if pd.isna(v) else str(v) for v in vals)
                                             for vals in grp[['대여소명','동','위도','경도']].drop_duplicates().itertuples(index=False, name=None))
                con.commit()
                print(f'  {batch}번째 묶음 / 이 파일 누적 {report["원본행"]:,}행', flush=True)
            reports.append(report)
        if stats['파일월과_대여월_불일치']:
            raise ValueError('파일명 월과 실제 대여 월이 다른 기록이 있습니다. 원본 제공 기준을 확인해야 하므로 결과 발행을 중단합니다.')
        hourly_path = OUT / 'tashu_station_hourly_all.csv'
        with hourly_path.with_suffix('.tmp').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['날짜','시간','대여소ID','대여건수','반납건수','순유출'])
            for d, h, sid, r, t in con.execute('SELECT * FROM counts ORDER BY day,hour,station'):
                writer.writerow([d,h,sid,r,t,r-t])
        hourly_path.with_suffix('.tmp').replace(hourly_path)
        info = pd.DataFrame(stations.values())
        if info.empty:
            raise ValueError('유성구 기록이 없습니다.')
        info['정보버전수'] = info['대여소ID'].map(lambda sid: len(versions[sid]))
        for c in ['최초기록일','최종기록일']:
            info[c] = pd.to_datetime(info[c]).dt.strftime('%Y-%m-%d')
        info.to_csv(OUT / 'tashu_station_info_all.csv', index=False, encoding='utf-8-sig')
        pd.DataFrame(reports).to_csv(OUT / 'tashu_file_audit_all.csv', index=False, encoding='utf-8-sig')
        missing_days = sorted(set(pd.date_range(START, END-pd.Timedelta(days=1)).strftime('%Y-%m-%d')) - rent_days)
        manifest = {}
        manifest.update({'source_start':'2025-12-01','source_end':'2026-10-31',
                         'analysis_start':'2025-12-02','analysis_end':'2026-10-31',
                         'file_count':len(files),'station_count':len(info),'stats':dict(stats),
                         'citywide_rental_missing_days':missing_days,
                         'note':'최초 월 경계의 반납 누락 영향을 줄이기 위해 12월 1일 제외. 이후 월 경계는 모든 원본의 실제 반납 시각으로 통합 집계.'})
        (OUT / 'tashu_all_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        print('\n[전체 집계 결과]')
        for k, v in stats.items(): print(f'{k}: {v:,}')
        print(f'대여소 수: {len(info):,}')
        print('대전 전체 대여 기록이 없는 날짜:', missing_days)
        print('저장 완료: data/processed/tashu_station_hourly_all.csv')
        print('저장 완료: data/processed/tashu_station_info_all.csv')
        print('저장 완료: data/processed/tashu_file_audit_all.csv')
        print('저장 완료: data/processed/tashu_all_manifest.json')
    finally:
        con.close()
    dbpath.unlink(missing_ok=True)


if __name__ == '__main__':
    run()
