from pathlib import Path
from urllib.request import urlopen
import json
import html

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "processed"
BOUNDARY_PATH = DATA_DIR / "yuseong_boundary_2013.geojson"

st.set_page_config(
    page_title="타슈 자전거 보충 검토",
    page_icon="🚲",
    layout="wide",
)

st.title("출근 시간 전 자전거 보충 우선 검토 지역")
st.caption(
    "유성구 · 2026년 10월 2~31일 중 월~금 21일 · 오전 7~9시 · 공휴일 포함"
)
st.write(
    "아침에 대여가 반납보다 많아 자전거가 반복적으로 빠져나가는 "
    "대여소를 보여줍니다."
)

summary_path = DATA_DIR / "tashu_morning_summary_named_202610.csv"
daily_path = DATA_DIR / "tashu_morning_daily_202610.csv"

if not summary_path.exists() or not daily_path.exists():
    st.error("data/processed 폴더의 분석 결과 CSV를 확인해주세요.")
    st.stop()

df = pd.read_csv(
    summary_path, encoding="utf-8-sig", dtype={"대여소ID": str}
)
daily = pd.read_csv(
    daily_path, encoding="utf-8-sig", dtype={"대여소ID": str}
)
daily["날짜"] = pd.to_datetime(daily["날짜"])

# 반올림된 평균 대신 합계로 순위를 계산
df["순유출합계"] = df["대여건수_합계"] - df["반납건수_합계"]

st.sidebar.header("조회 조건")
dong = st.sidebar.selectbox(
    "동 선택",
    ["전체"] + sorted(df["동"].dropna().unique().tolist()),
)
top_n = st.sidebar.selectbox("표시할 대여소 수", [5, 10, 15], index=0)

view = df.copy()
if dong != "전체":
    view = view[view["동"].eq(dong)]

# 동일한 21일 자료이므로 순유출 합계 순위는 평균 순위와 같음
# 동률이면 순유출 발생일수, 마지막으로 ID 순서 사용
ranked = (
    view[view["순유출합계"] > 0]
    .sort_values(
        ["순유출합계", "순유출_발생일수", "대여소ID"],
        ascending=[False, False, True],
    )
    .head(top_n)
    .copy()
)
ranked.insert(0, "순위", range(1, len(ranked) + 1))

if ranked.empty:
    st.info("선택한 지역에는 평균 순유출이 양수인 대여소가 없습니다.")
    st.stop()

scope = "유성구 전체" if dong == "전체" else dong

st.subheader(f"{scope} 우선 검토 대여소")
st.caption("순위는 조회 범위 안에서 아침 일평균 순유출이 큰 순서입니다.")

# 첫 화면에는 장소만 표시
st.dataframe(
    ranked[["순위", "동", "대여소명"]].rename(
        columns={"동": "동 이름", "대여소명": "대여소"}
    ),
    hide_index=True,
    use_container_width=True,
)

first = ranked.iloc[0]
st.success(
    f"1순위 검토: {first['대여소명']} — "
    f"분석일 {int(first['분석일수'])}일 중 "
    f"{int(first['순유출_발생일수'])}일에 대여가 반납보다 많았습니다."
)

# 유성구 경계만 있는 지도: 다른 지역 배경지도는 표시하지 않음
st.subheader("우선 검토 대여소 위치")
st.caption("번호는 위 목록의 순위입니다. 번호를 누르면 선정 근거가 나옵니다.")

try:
    if BOUNDARY_PATH.exists():
        boundary = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    else:
        url = (
            "https://raw.githubusercontent.com/southkorea/"
            "southkorea-maps/master/kostat/2013/json/"
            "skorea_municipalities_geo_simple.json"
        )
        with urlopen(url, timeout=30) as response:
            source = json.load(response)

        features = [
            feature for feature in source["features"]
            if feature["properties"].get("name") == "유성구"
        ]
        if len(features) != 1:
            raise ValueError("유성구 경계를 하나로 확인하지 못했습니다.")

        boundary = {
            "type": "FeatureCollection",
            "features": features,
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BOUNDARY_PATH.write_text(
            json.dumps(boundary, ensure_ascii=False),
            encoding="utf-8",
        )

    # tiles=None: 유성구 윤곽과 대여소만 표시
    map_view = folium.Map(
        location=[36.37, 127.34],
        tiles=None,
        zoom_start=12,
    )

    boundary_layer = folium.GeoJson(
        boundary,
        name="유성구 경계",
        style_function=lambda feature: {
            "color": "#2563eb",
            "weight": 2,
            "fillColor": "#eff6ff",
            "fillOpacity": 0.7,
        },
        tooltip="유성구 · 2013년 기준 임시 경계",
    ).add_to(map_view)

    map_view.fit_bounds(boundary_layer.get_bounds())

    invalid_coordinates = 0

    for _, row in ranked.iterrows():
        lat, lon = row["위도"], row["경도"]

        if (
            pd.isna(lat) or pd.isna(lon)
            or not 33 <= lat <= 39
            or not 124 <= lon <= 132
        ):
            invalid_coordinates += 1
            continue

        rank = int(row["순위"])
        name = html.escape(str(row["대여소명"]))
        dong_name = html.escape(str(row["동"]))

        popup = (
            f"<b>{rank}순위 · {name}</b><br>"
            f"원본 동: {dong_name}<br><br>"
            f"아침 일평균 대여: {row['일평균_대여건수']:.2f}건<br>"
            f"아침 일평균 반납: {row['일평균_반납건수']:.2f}건<br>"
            f"일평균 순유출: {row['일평균_순유출']:.2f}건<br>"
            f"순유출 발생: {int(row['순유출_발생일수'])}"
            f"/{int(row['분석일수'])}일<br><br>"
            "출근 전 배치 상태 점검 후보<br>"
            "실제 부족 대수를 의미하지 않음"
        )

        folium.Marker(
            location=[lat, lon],
            tooltip=f"{rank}순위 · {name}",
            popup=folium.Popup(popup, max_width=320),
            icon=folium.DivIcon(
                icon_size=(30, 30),
                icon_anchor=(15, 15),
                html=(
                    '<div style="background:#2563eb;color:white;'
                    'border:2px solid white;border-radius:50%;'
                    'width:30px;height:30px;text-align:center;'
                    'line-height:26px;font-weight:bold;'
                    'box-sizing:border-box;">'
                    f"{rank}</div>"
                ),
            ),
        ).add_to(map_view)

    st_folium(map_view, height=430, use_container_width=True)

    if invalid_coordinates:
        st.warning(f"좌표 확인이 필요한 {invalid_coordinates}곳은 지도에서 제외했습니다.")

    st.caption(
        "경계 출처: southkorea-maps / 통계청 2013년 자료. "
        "화면 구성 확인용이며 최신 경계와의 일치는 아직 검증하지 않았습니다."
    )

except Exception as error:
    st.warning(f"경계 지도를 불러오지 못했습니다: {error}")

with st.expander("선정 방식과 상세 수치 보기"):
    st.write(
        "① 날짜별 오전 7~9시 대여·반납 건수를 합산합니다.\n\n"
        "② 대여건수에서 반납건수를 뺀 순유출을 계산합니다.\n\n"
        "③ 분석일 21일의 평균 순유출이 큰 순서로 표시합니다. "
        "동률이면 순유출 발생일수가 많은 곳을 먼저 표시합니다."
    )
    st.dataframe(
        ranked[[
            "순위", "대여소ID", "동", "대여소명",
            "일평균_대여건수", "일평균_반납건수",
            "일평균_순유출", "순유출_발생일수",
            "순유출_발생일비율_pct", "정보버전수",
        ]],
        hide_index=True,
        use_container_width=True,
    )
    st.warning(
        "이 순위에는 유동인구·주민등록인구·실제 재고·운영 차량의 "
        "재배치를 반영하지 않았습니다. 보충 우선 검토를 위한 탐색 결과입니다."
    )

with st.expander("대여소별 날짜별 그래프 보기"):
    options = view.sort_values("대여소ID").copy()
    labels = {
        row["대여소ID"]: f"{row['대여소명']} [{row['대여소ID']}]"
        for _, row in options.iterrows()
    }

    station_id = st.selectbox(
        "대여소 선택",
        list(labels),
        format_func=lambda value: labels[value],
    )

    history = daily[
        daily["대여소ID"].eq(station_id)
    ].sort_values("날짜")

    st.write("날짜별 오전 7~9시 대여·반납")
    st.line_chart(
        history.set_index("날짜")[["대여건수", "반납건수"]]
    )

    st.write("날짜별 순유출")
    st.bar_chart(history.set_index("날짜")[["순유출"]])

with st.expander("분석 범위와 자료 해석"):
    st.write(
        "- 월~금 기준이며 공휴일을 별도로 제외하지 않았습니다.\n"
        "- 10월 1일은 월 경계 반납 누락 가능성 때문에 제외했습니다.\n"
        "- 기록이 없는 날짜는 0건으로 처리했으며 운영 여부는 미확인입니다.\n"
        "- 동·좌표는 대여 이력 원본 기준이며 최신 관측 정보를 사용합니다.\n"
        "- 대여소 이름에 들어간 동과 원본 동이 다를 수 있습니다.\n"
        "- 이용하지 못한 수요와 운영 차량의 보충·회수는 알 수 없습니다."
    )