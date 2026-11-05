from pathlib import Path
from urllib.request import urlopen
import json
import html

import pandas as pd
import streamlit as st
import altair as alt
import folium
from streamlit_folium import st_folium


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "processed"

HOURLY_PATH = DATA_DIR / "tashu_station_hourly_202610.csv"
INFO_PATH = DATA_DIR / "tashu_morning_summary_named_202610.csv"
BOUNDARY_PATH = DATA_DIR / "yuseong_boundary_2013.geojson"

BOUNDARY_URL = (
    "https://raw.githubusercontent.com/southkorea/"
    "southkorea-maps/master/kostat/2013/json/"
    "skorea_municipalities_geo_simple.json"
)

st.set_page_config(
    page_title="유성구 타슈 이용 분석",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #f5f7fb;
    }

    .block-container {
        max-width: 1450px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    section[data-testid="stSidebar"] {
        min-width: 300px !important;
        max-width: 300px !important;
        background-color: #eaf0f8;
    }

    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label {
        font-size: 16px !important;
    }

    [data-testid="stWidgetLabel"] p {
        font-size: 17px !important;
        font-weight: 600;
    }

    [data-testid="stCaptionContainer"] p {
        font-size: 15px !important;
        color: #526176;
    }

    h2 {
        font-size: 27px !important;
        color: #142d4e;
    }

    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #dce4ef;
        border-radius: 14px;
        padding: 18px;
    }

    [data-testid="stMetricLabel"] p {
        font-size: 16px !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 30px !important;
    }

    .page-title {
        font-size: 40px;
        font-weight: 800;
        color: #142d4e;
        margin-bottom: 10px;
        line-height: 1.3;
    }

    .page-description {
        font-size: 18px;
        color: #526176;
        margin-bottom: 12px;
        line-height: 1.6;
    }

    .section-line {
        border-top: 2px solid #ccd8e8;
        margin: 32px 0 26px;
    }

    .station-row {
        background: white;
        border: 1px solid #dce4ef;
        border-radius: 10px;
        padding: 11px 13px;
        margin-bottom: 8px;
        display: flex;
        align-items: flex-start;
        gap: 10px;
    }
    .station-rank {
        background: #e8f0ff;
        color: #2455bc;
        font-size: 15px;
        font-weight: 700;
        border-radius: 7px;
        min-width: 32px;
        height: 30px;
        line-height: 30px;
        text-align: center;
        flex-shrink: 0;
    }
    .station-name {
        color: #142d4e;
        font-size: 16px;
        font-weight: 700;
        line-height: 1.45;
        overflow-wrap: anywhere;
    }
    .station-meta {
        font-size: 13px;
        color: #526176;
        margin-top: 3px;
        line-height: 1.4;
    }

    @media (max-width: 700px) {
        .page-title {
            font-size: 29px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def divider():
    st.markdown(
        '<div class="section-line"></div>',
        unsafe_allow_html=True,
    )


def safe_text(value):
    if pd.isna(value):
        return "정보 없음"
    return html.escape(str(value))


def make_flow_chart(frame):
    """시간별 평균 대여·반납 그래프."""
    plot_data = (
        frame[["대여건수", "반납건수"]]
        .rename(columns={
            "대여건수": "일평균 대여",
            "반납건수": "일평균 반납",
        })
        .rename_axis("시간")
        .reset_index()
        .melt(
            id_vars="시간",
            var_name="구분",
            value_name="일평균 건수",
        )
    )

    return (
        alt.Chart(plot_data)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "시간:Q",
                title="시간 — 17시는 17:00~18:00",
                scale=alt.Scale(domain=[0, 23]),
                axis=alt.Axis(
                    values=list(range(24)),
                    format="d",
                    labelOverlap=True,
                ),
            ),
            y=alt.Y(
                "일평균 건수:Q",
                title="시간대별 하루 평균 이용 건수",
                scale=alt.Scale(zero=True),
            ),
            color=alt.Color(
                "구분:N",
                scale=alt.Scale(
                    domain=["일평균 대여", "일평균 반납"],
                    range=["#2563eb", "#f08a24"],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("시간:Q", title="시작 시각", format="d"),
                alt.Tooltip("구분:N"),
                alt.Tooltip("일평균 건수:Q", format=".2f"),
            ],
        )
        .properties(height=340)
        .configure_axis(labelFontSize=14, titleFontSize=15)
        .configure_legend(labelFontSize=16)
        .configure_view(stroke=None)
    )


def load_boundary():
    """저장된 경계를 사용하고, 없으면 유성구 경계만 추출해 저장."""
    if BOUNDARY_PATH.exists():
        return json.loads(
            BOUNDARY_PATH.read_text(encoding="utf-8")
        )

    with urlopen(BOUNDARY_URL, timeout=30) as response:
        source = json.load(response)

    features = [
        feature
        for feature in source["features"]
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
    return boundary


# --------------------------------------------------
# 제목
# --------------------------------------------------
st.markdown(
    """
    <div class="page-title">유성구 타슈 24시간 이용 분석</div>
    <div class="page-description">
        언제, 어디에서 많이 빌리고 반납했는지 확인합니다.
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "분석 기간: 2026년 10월 2~31일 · "
    "10월 1일은 월 경계 반납 누락 가능성 때문에 제외"
)


# --------------------------------------------------
# 데이터 읽기
# --------------------------------------------------
if not HOURLY_PATH.exists() or not INFO_PATH.exists():
    st.error("분석에 필요한 CSV 파일이 없습니다.")
    st.write("다음 두 파일이 data/processed 폴더에 있어야 합니다.")
    st.code(
        "tashu_station_hourly_202610.csv\n"
        "tashu_morning_summary_named_202610.csv"
    )
    st.stop()

df = pd.read_csv(
    HOURLY_PATH,
    encoding="utf-8-sig",
    dtype={"대여소ID": str},
)
df["날짜"] = pd.to_datetime(df["날짜"])

# 오전 분석 파일에서는 장소 정보만 사용
# 오전 대여·반납 집계값은 사용하지 않음
info = pd.read_csv(
    INFO_PATH,
    encoding="utf-8-sig",
    dtype={"대여소ID": str},
)[["대여소ID", "대여소명", "동", "위도", "경도"]]

if info["대여소ID"].duplicated().any():
    st.error("대여소 정보에 중복 ID가 있습니다.")
    st.stop()

for column in ["위도", "경도"]:
    info[column] = pd.to_numeric(info[column], errors="coerce")

info["대여소명"] = info["대여소명"].fillna("이름 미확인")
info["동"] = info["동"].fillna("동 미확인")

unknown_ids = set(df["대여소ID"]) - set(info["대여소ID"])
if unknown_ids:
    st.error(
        f"장소 정보가 연결되지 않은 대여소가 {len(unknown_ids)}개 있습니다."
    )
    st.write(sorted(unknown_ids))
    st.stop()


# --------------------------------------------------
# 왼쪽 조회 조건
# --------------------------------------------------
st.sidebar.header("조회 조건")

day_type = st.sidebar.selectbox(
    "요일 구분",
    ["전체", "월~금", "토·일"],
)
st.sidebar.caption("공휴일은 따로 구분하지 않고 요일에 포함합니다.")

dong = st.sidebar.selectbox(
    "동 선택",
    ["전체"] + sorted(info["동"].unique().tolist()),
)

hours = st.sidebar.slider(
    "순위·지도에 반영할 시간",
    min_value=0,
    max_value=23,
    value=(0, 23),
)
st.sidebar.caption("기본값은 하루 전체입니다. 23시는 23:00~24:00입니다.")

ranking_type = st.sidebar.selectbox(
    "분석 종류",
    [
        "대여가 많은 곳",
        "반납이 많은 곳",
        "순유출이 큰 곳",
        "자전거 보충 검토",
    ],
)

top_n = 10
st.sidebar.caption("각 분석의 상위 10곳을 표시합니다.")

exclude_center = st.sidebar.checkbox(
    "관제센터 제외",
    value=True,
)
st.sidebar.caption(
    "이름에 ‘관제센터’가 있는 장소를 그래프·순위에서 제외합니다. "
    "다른 관리용 장소는 별도 확인이 필요합니다."
)


# --------------------------------------------------
# 날짜와 장소 필터
# --------------------------------------------------
dates = pd.date_range("2026-10-02", "2026-10-31", freq="D")

if day_type == "월~금":
    dates = dates[dates.dayofweek < 5]
elif day_type == "토·일":
    dates = dates[dates.dayofweek >= 5]

n_days = len(dates)

center_mask = (
    info["대여소명"]
    .str.replace(r"\s+", "", regex=True)
    .str.contains("관제센터", regex=False)
)

excluded_centers = info.loc[center_mask].copy()
area_info = info.copy()

if exclude_center:
    area_info = area_info.loc[~center_mask].copy()

if dong != "전체":
    area_info = area_info[area_info["동"].eq(dong)]

area = df[
    df["날짜"].isin(dates)
    & df["대여소ID"].isin(area_info["대여소ID"])
].copy()

if area.empty:
    st.info("선택한 조건에서 확인된 이용 기록이 없습니다.")
    st.stop()

scope = "유성구 전체" if dong == "전체" else dong
center_label = "관제센터 제외" if exclude_center else "관제센터 포함"

st.caption(
    f"현재 조회: {scope} · {day_type} {n_days}일 · {center_label}"
)


# --------------------------------------------------
# 1. 24시간 전체 그래프
# --------------------------------------------------
divider()
st.subheader("01. 언제 많이 이용했을까?")
st.caption(
    "시간 선택과 관계없이 하루 전체를 보여줍니다. "
    "요일별 날짜 수 차이를 보정하기 위해 하루 평균으로 비교합니다."
)

hourly = (
    area.groupby("시간")[["대여건수", "반납건수"]]
    .sum()
    .reindex(range(24), fill_value=0)
)
hourly_average = hourly / n_days

c1, c2, c3 = st.columns(3)

c1.metric(
    "하루 평균 대여",
    f"{area['대여건수'].sum() / n_days:,.1f}건",
)
c2.metric(
    "하루 평균 반납",
    f"{area['반납건수'].sum() / n_days:,.1f}건",
)

if hourly["대여건수"].sum() > 0:
    peak_value = hourly["대여건수"].max()
    peak_hours = hourly.index[
        hourly["대여건수"].eq(peak_value)
    ].tolist()

    peak = int(peak_hours[0])
    c3.metric(
        "대여 최다 시간대",
        f"{peak:02d}:00~{peak + 1:02d}:00",
    )
    if len(peak_hours) > 1:
        st.caption(
            "최다 대여 시간대 동률: "
            + ", ".join(f"{int(h):02d}시" for h in peak_hours)
        )
else:
    c3.metric("대여 최다 시간대", "대여 기록 없음")

st.altair_chart(
    make_flow_chart(hourly_average),
    use_container_width=True,
)


# --------------------------------------------------
# 2. 선택한 시간대의 대여소별 순위
# --------------------------------------------------
selected = area[
    area["시간"].between(hours[0], hours[1])
].copy()

totals = selected.groupby("대여소ID")[
    ["대여건수", "반납건수"]
].sum()

summary = area_info.merge(
    totals,
    left_on="대여소ID",
    right_index=True,
    how="left",
    validate="one_to_one",
)

for column in ["대여건수", "반납건수"]:
    summary[column] = summary[column].fillna(0).astype(int)

summary["순유출"] = summary["대여건수"] - summary["반납건수"]
summary["일평균_대여"] = summary["대여건수"] / n_days
summary["일평균_반납"] = summary["반납건수"] / n_days
summary["일평균_순유출"] = summary["순유출"] / n_days

# --------------------------------------------------
# 보충 검토: 대여소 × 날짜 × 선택 시간별 순수요 계산
# --------------------------------------------------
if ranking_type == "자전거 보충 검토":
    station_ids = area_info["대여소ID"].tolist()
    selected_hours = list(range(hours[0], hours[1] + 1))

    # 이용 기록이 없는 날짜·시간도 포함
    # 0건은 이용 기록이 없다는 뜻이며 운영 여부는 미확인
    full_index = pd.MultiIndex.from_product(
        [station_ids, dates, selected_hours],
        names=["대여소ID", "날짜", "시간"],
    )

    daily_hourly = (
        selected.groupby(["대여소ID", "날짜", "시간"])[
            ["대여건수", "반납건수"]
        ]
        .sum()
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    daily_hourly["순수요"] = daily_hourly["대여건수"] - daily_hourly["반납건수"]
    daily_hourly["순유출발생"] = daily_hourly["순수요"].gt(0)

    shortage_stats = (
        daily_hourly.groupby(["대여소ID", "시간"], as_index=False)
        .agg(
            평균순수요=("순수요", "mean"),
            표준편차=("순수요", "std"),
            해당시간_평균대여=("대여건수", "mean"),
            해당시간_평균반납=("반납건수", "mean"),
            분석일수=("날짜", "size"),
            순유출발생일수=("순유출발생", "sum"),
        )
    )
    # pandas std는 표본 표준편차(ddof=1)를 사용합니다.
    shortage_stats["표준편차"] = shortage_stats["표준편차"].fillna(0)
    shortage_stats["여유분"] = 1.65 * shortage_stats["표준편차"]
    shortage_stats["기준량"] = (
        shortage_stats["평균순수요"] + shortage_stats["여유분"]
    ).where(shortage_stats["평균순수요"].ge(0), 0)
    shortage_stats["순유출발생비율_pct"] = (
        shortage_stats["순유출발생일수"] / shortage_stats["분석일수"] * 100
    )

    # 시간별 기준량 중 최대값을 대표값으로 사용합니다.
    # 같은 값이면 먼저 시작하는 시간대를 표시합니다.
    representative = (
        shortage_stats.sort_values(
            ["대여소ID", "기준량", "시간"],
            ascending=[True, False, True],
        )
        .drop_duplicates("대여소ID")
        .rename(columns={"시간": "검토시간"})
    )
    summary = summary.merge(
        representative, on="대여소ID", how="left", validate="one_to_one"
    )

metric = {
    "대여가 많은 곳": "대여건수",
    "반납이 많은 곳": "반납건수",
    "순유출이 큰 곳": "순유출",
    "자전거 보충 검토": "기준량",
}[ranking_type]

ranked = (
    summary[summary[metric] > 0]
    .sort_values(
        [metric, "대여소ID"],
        ascending=[False, True],
    )
    .head(top_n)
    .copy()
)
ranked.insert(0, "순위", range(1, len(ranked) + 1))

period = f"{hours[0]:02d}:00~{hours[1] + 1:02d}:00"

divider()
st.subheader(f"02. {ranking_type} TOP 10")

if ranking_type == "자전거 보충 검토":
    st.caption(
        f"{scope} · {period} · {day_type} {n_days}일 기준. "
        "각 대여소의 시간별 기준량 중 최대값으로 순위를 정합니다. "
        "동률은 대여소 ID 순서로 표시합니다."
    )
    st.info(
        "평균 순수요가 0 이상인 시간에 "
        "‘평균 순수요 + 1.65 × 표준편차’를 적용했습니다. "
        "보충 운영을 검토할 후보이며, 실제 부족 대수나 추가 배치 대수가 아닙니다. "
        "1.65는 중요도 가중치가 아니라 변동성 여유 계수이며, "
        "이 자료에서 95%의 서비스 수준을 보장한다는 뜻은 아닙니다."
    )

elif ranking_type == "순유출이 큰 곳":
    st.caption(
        f"{scope} · {period} · {day_type} {n_days}일 합계 기준. "
        "동률은 대여소 ID 순서로 표시합니다."
    )
    st.info(
        "순유출은 대여건수−반납건수입니다. "
        "하루 합계에서는 시간대별 유출·유입이 상쇄될 수 있습니다."
    )

else:
    st.caption(
        f"{scope} · {period} · {day_type} {n_days}일 합계 기준. "
        "동률은 대여소 ID 순서로 표시합니다."
    )
    st.caption(
        "실제로 완료된 이용 기록의 순위이며, "
        "시설 부족이나 보충 우선순위를 의미하지 않습니다."
    )
list_column, map_column = st.columns([1, 1.7], gap="large")

with list_column:
    st.markdown("**후보 목록**" if ranking_type == "자전거 보충 검토" else "**대여소 순위**")
    if ranked.empty:
        st.info("선택한 조건에서 표시할 대여소가 없습니다.")
    else:
        for _, row in ranked.iterrows():
            if ranking_type == "자전거 보충 검토":
                h = int(row["검토시간"])
                note = f"검토 시간 {h:02d}~{h + 1:02d}시 · 기준량 {row['기준량']:.1f}"
            else:
                note = f"{metric} {int(row[metric]):,}건 · 선택 기간 합계"
            st.markdown(
                f'<div class="station-row">'
                f'<span class="station-rank">{int(row["순위"])}</span>'
                f'<div><div class="station-name">'
                f'{safe_text(row["동"])} · {safe_text(row["대여소명"])}'
                f'</div><div class="station-meta">{safe_text(note)}</div></div></div>',
                unsafe_allow_html=True,
            )

with map_column:
    st.markdown("**대여소 위치 · 번호는 왼쪽 순위와 같습니다**")
    if ranked.empty:
        st.info("순위에 표시할 대여소가 없어 지도를 생략했습니다.")
    else:
        try:
            boundary = None
            try:
                with st.spinner("유성구 지도를 준비하고 있습니다..."):
                    boundary = load_boundary()
            except Exception as boundary_error:
                st.warning("유성구 경계를 읽지 못해 배경 지도와 대여소만 표시합니다.")
                with st.expander("경계 파일 오류 내용"):
                    st.code(str(boundary_error))

            map_view = folium.Map(
                location=[36.37, 127.34],
                tiles="OpenStreetMap",
                zoom_start=12,
                control_scale=True,
                scrollWheelZoom=True,
            )

            if boundary is not None:
                boundary_layer = folium.GeoJson(
                    boundary,
                    name="유성구 경계",
                    style_function=lambda feature: {
                        "color": "#2563eb",
                        "weight": 3,
                        "opacity": 0.9,
                        "fill": False,
                        "fillOpacity": 0,
                    },
                ).add_to(map_view)

                map_view.fit_bounds(
                    boundary_layer.get_bounds(),
                    padding=(20, 20),
                )

            invalid_coordinates = 0

            for _, row in ranked.iterrows():
                lat = row["위도"]
                lon = row["경도"]

                if (
                    pd.isna(lat)
                    or pd.isna(lon)
                    or not 33 <= lat <= 39
                    or not 124 <= lon <= 132
                ):
                    invalid_coordinates += 1
                    continue

                rank = int(row["순위"])
                name = safe_text(row["대여소명"])
                dong_name = safe_text(row["동"])

                popup = f"""
                <div style="font-size:16px;line-height:1.8;">
                    <b>{rank}위 · {name}</b><br>
                    동: {dong_name}<br>
                    분석 시간: {period}<br>
                    대여: {int(row["대여건수"]):,}건<br>
                    반납: {int(row["반납건수"]):,}건<br>
                    순유출(대여−반납): {int(row["순유출"]):,}건
                </div>
                """

                if ranking_type == "자전거 보충 검토":
                    review_hour = int(row["검토시간"])

                    popup += f"""
                    <hr>
                    <div style="font-size:15px;line-height:1.8;">
                        <b>보충 검토 선정 근거</b><br>
                        검토 시간:
                        {review_hour:02d}:00~{review_hour + 1:02d}:00<br>
                        해당 시간 평균 순수요:
                        {row["평균순수요"]:.2f}건<br>
                        변동성 여유분:
                        {row["여유분"]:.2f}건<br>
                        기준량:
                        {row["기준량"]:.2f}대 상당/1시간<br>
                        순유출 발생:
                        {int(row["순유출발생일수"])}일 /
                        {int(row["분석일수"])}일<br><br>
                        실제 추가 배치 대수가 아닙니다.
                    </div>
                    """

                folium.Marker(
                    location=[lat, lon],
                    tooltip=f"{rank}위 · {name}",
                    popup=folium.Popup(popup, max_width=360),
                    icon=folium.DivIcon(
                        icon_size=(36, 36),
                        icon_anchor=(18, 18),
                        html=(
                            '<div style="background:#2563eb;color:white;'
                            'border:3px solid white;border-radius:50%;'
                            'width:36px;height:36px;line-height:30px;'
                            'text-align:center;font-size:17px;'
                            'font-weight:bold;box-sizing:border-box;'
                            'box-shadow:0 2px 8px #64748b;">'
                            f"{rank}</div>"
                        ),
                    ),
                ).add_to(map_view)

            st_folium(
                map_view,
                height=780,
                use_container_width=True,
                returned_objects=[],
            )

            if invalid_coordinates:
                st.warning(
                    f"좌표 확인이 필요한 {invalid_coordinates}곳은 지도에서 제외했습니다."
                )

            st.caption(
                "경계 출처: southkorea-maps / 통계청 2013년 자료. "
                "화면 확인용 임시 경계이며 최신 경계와의 일치는 미검증입니다. "
                "좌표가 실제 유성구 경계 내부인지에 대한 공간 검증도 별도로 필요합니다."
            )

        except Exception as error:
            st.warning(
                "경계 지도를 불러오지 못했습니다. "
                "인터넷 연결을 확인한 후 페이지를 새로고침해주세요."
            )
            with st.expander("지도 오류 내용 보기"):
                st.code(str(error))


# --------------------------------------------------
# 4. 상세 정보
# --------------------------------------------------
divider()
st.subheader("03. 상세 분석")

with st.expander("전체 대여소 수치와 CSV 다운로드"):
    detail = summary.sort_values(
        [metric, "대여소ID"],
        ascending=[False, True],
    )
    detail_columns = [
        "대여소ID", "동", "대여소명",
        "대여건수", "반납건수", "순유출",
        "일평균_대여", "일평균_반납", "일평균_순유출",
    ]
    if ranking_type == "자전거 보충 검토":
        detail_columns += [
            "검토시간", "해당시간_평균대여", "해당시간_평균반납",
            "평균순수요", "표준편차", "여유분", "기준량",
            "순유출발생일수", "분석일수", "순유출발생비율_pct",
        ]
    detail = detail[detail_columns].round(2)

    st.caption(
        f"{scope} · {day_type} · {period} · {center_label}"
    )
    st.dataframe(
        detail,
        hide_index=True,
        use_container_width=True,
    )

    st.download_button(
        "현재 조회 결과 CSV 다운로드",
        data=detail.to_csv(index=False).encode("utf-8-sig"),
        file_name="tashu_filtered_station_summary.csv",
        mime="text/csv",
    )

with st.expander("대여소 한 곳의 24시간 이용 흐름"):
    options = area_info.sort_values(
        ["대여소명", "대여소ID"]
    )

    labels = {
        row["대여소ID"]: (
            f"{row['대여소명']} [{row['대여소ID']}]"
        )
        for _, row in options.iterrows()
    }

    station_id = st.selectbox(
        "확인할 대여소",
        list(labels),
        format_func=lambda value: labels[value],
    )

    station_hourly = (
        area[area["대여소ID"].eq(station_id)]
        .groupby("시간")[["대여건수", "반납건수"]]
        .sum()
        .reindex(range(24), fill_value=0)
        / n_days
    )

    st.caption(
        f"{day_type} {n_days}일 기준 하루 평균입니다. "
        "이 그래프는 시간 선택과 관계없이 24시간을 표시합니다."
    )

    st.altair_chart(
        make_flow_chart(station_hourly),
        use_container_width=True,
    )

    net = station_hourly.copy()
    net["일평균 순유출"] = net["대여건수"] - net["반납건수"]
    net = net.rename_axis("시간").reset_index()

    st.write("시간별 일평균 순유출")
    st.caption("양수는 대여 우세, 음수는 반납 우세를 뜻합니다.")

    net_chart = (
        alt.Chart(net)
        .mark_bar()
        .encode(
            x=alt.X(
                "시간:O",
                title="시간",
                sort=list(range(24)),
            ),
            y=alt.Y(
                "일평균 순유출:Q",
                title="대여 − 반납 (건/일)",
            ),
            color=alt.condition(
                alt.datum["일평균 순유출"] > 0,
                alt.value("#2563eb"),
                alt.value("#f08a24"),
            ),
            tooltip=[
                alt.Tooltip("시간:O"),
                alt.Tooltip("일평균 순유출:Q", format=".2f"),
            ],
        )
        .properties(height=260)
        .configure_axis(labelFontSize=14, titleFontSize=15)
        .configure_view(stroke=None)
    )

    st.altair_chart(net_chart, use_container_width=True)

with st.expander("관제센터 분류 확인"):
    st.write(
        "이름에 ‘관제센터’가 들어간 장소를 관리용 장소로 구분했습니다. "
        "개별 기록이 관리 업무로 발생했는지는 확인하지 않았습니다."
    )

    if excluded_centers.empty:
        st.write("이름으로 식별된 관제센터가 없습니다.")
    else:
        st.dataframe(
            excluded_centers[["대여소ID", "동", "대여소명"]],
            hide_index=True,
            use_container_width=True,
        )

    st.caption(
        "제외 옵션을 켜면 해당 장소의 대여·반납 사건만 제외합니다. "
        "다른 대여소에서 발생한 같은 이동의 반대편 사건은 남아 있습니다."
    )

with st.expander("분석 기준과 한계"):
    st.write(
        "- 오전을 가정하지 않고 24시간 전체를 기본으로 분석합니다.\n"
        "- 월~금과 토·일은 각각의 달력상 날짜 수로 나눠 비교합니다.\n"
        "- 공휴일은 별도 구분하지 않습니다.\n"
        "- 기록이 없는 시간은 0건으로 처리하며 실제 운영 여부는 미확인입니다.\n"
        "- 대여·반납 건수는 이용 횟수이며 이용자 수가 아닙니다.\n"
        "- 현재 분석은 2026년 10월 2~31일에 한정됩니다.\n"
        "- 원본 중복과 전체 수집 누락은 별도 검증이 필요합니다.\n"
        "- 동과 위치는 대여 이력에서 추출한 최신 관측 정보를 사용합니다.\n"
        "- 유동인구·주민등록인구·실제 재고는 현재 순위에 포함하지 않습니다.\n"
        "- 이용량이 많다는 이유만으로 시설이 부족하다고 판단하지 않습니다.\n"
        "- 순유출은 실제 재고 감소나 추가 배치 권장 대수를 뜻하지 않습니다.\n"
        "- 정책 후보 선정에는 날짜별 반복성, 주변 대여소 거리 등을 함께 검토해야 합니다."
    )
    
if ranking_type == "자전거 보충 검토" and not ranked.empty:
    with st.expander("보충 검토 TOP 10 선정 이유 보기"):
        reasons = ranked[[
            "순위", "동", "대여소명", "검토시간",
            "해당시간_평균대여", "해당시간_평균반납",
            "평균순수요", "표준편차", "여유분", "기준량",
            "순유출발생일수", "분석일수",
        ]].copy()

        reasons["검토시간"] = reasons["검토시간"].map(
            lambda h: f"{int(h):02d}:00~{int(h) + 1:02d}:00"
        )

        st.dataframe(
            reasons.round(2),
            hide_index=True,
            use_container_width=True,
        )

        st.caption(
            "각 행의 수치는 해당 대여소의 검토 시간 1시간에 대한 값입니다. "
            "큰 기준량은 평균 순유출 또는 날짜별 변동성이 커서 발생할 수 있습니다."
        )

        labels = {
            row["대여소ID"]: (
                f"{int(row['순위'])}위 · {row['대여소명']}"
            )
            for _, row in ranked.iterrows()
        }

        chosen_id = st.selectbox(
            "날짜별 근거를 볼 후보",
            list(labels),
            format_func=lambda value: labels[value],
            key="shortage_reason_station",
        )

        chosen = ranked[
            ranked["대여소ID"].eq(chosen_id)
        ].iloc[0]
        review_hour = int(chosen["검토시간"])

        records = daily_hourly[
            daily_hourly["대여소ID"].eq(chosen_id)
            & daily_hourly["시간"].eq(review_hour)
        ].sort_values("날짜")

        st.write(
            f"**{review_hour:02d}:00~{review_hour + 1:02d}:00 "
            "날짜별 순유출**"
        )
        st.bar_chart(
            records.set_index("날짜")[["순수요"]]
        )

        st.write(
            "검토 조치: 이 시간 전후의 재고와 기존 보충 일정을 확인하여 "
            "자전거 재배치 운영을 검토합니다. "
            "특정 날짜에만 값이 크다면 해당 날짜의 이용 특성을 함께 확인합니다."
        )

        st.markdown(
            "[계산식 참고: 이은탁·손봉수(2019), "
            "이용수요 기반의 서울시 공공자전거 재배치전략 도출]"
            "(https://www.jkst.or.kr/articles/xml/RY4Q/)"
        )
        st.caption(
            "24시간 중 최대 기준량으로 후보를 정렬한 것은 "
            "본 프로젝트의 추가 탐색 기준입니다. "
            "EJOR 논문의 재고 최적화 모형을 구현한 것은 아닙니다."
        )

        st.download_button(
            "보충 검토 TOP 10 근거 CSV 다운로드",
            data=reasons.round(3).to_csv(
                index=False
            ).encode("utf-8-sig"),
            file_name="tashu_shortage_review_top10.csv",
            mime="text/csv",
        )