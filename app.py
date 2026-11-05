from pathlib import Path

import pandas as pd
import streamlit as st

folder = Path(__file__).resolve().parent


def read_csv(filename):
    return pd.read_csv(folder / filename, encoding="utf-8-sig")


st.set_page_config(page_title="유성구 타슈 정책 분석", layout="wide")
st.title("유성구 타슈 정책 분석")
st.caption("타슈 재고는 2026년 11월 5일 09:30 관측값이며, 유동인구는 2022년 자료입니다.")

stations = read_csv("tashu_yuseong_clean.csv")
alternatives = read_csv("tashu_alternatives.csv")
replenish = read_csv("tashu_replenishment_review.csv")
facility = read_csv("tashu_facility_review.csv")
unmatched = read_csv("tashu_station_check_needed.csv")

tab1, tab2 = st.tabs(["자전거 보충 검토", "대여·반납소 확충 검토"])

with tab1:
    distance = "대체_대여소_직선거리_m"

    a, b, c = st.columns(3)
    a.metric("유성구 관측 대여소", f"{len(stations)}곳")
    b.metric("자전거 0대 대여소", f"{stations['parking_count'].eq(0).sum()}곳")
    c.metric("0대이며 대체 대여소가 500m 초과", f"{alternatives[distance].gt(500).sum()}곳")

    st.subheader("어느 동에서 보충을 먼저 검토할까?")
    chart = replenish.head(10).set_index("법정동명")
    st.bar_chart(chart[["자전거_0대_대여소_수", "대체거리_500m_초과_수"]])

    st.subheader("대체 대여소가 먼 지점")
    dongs = sorted(alternatives["법정동명"].dropna().unique())
    selected = st.selectbox("법정동 선택", ["전체", *dongs])
    threshold = st.radio("대체 대여소까지 직선거리 기준", [300, 500], index=1, horizontal=True)

    candidates = alternatives.loc[alternatives[distance].gt(threshold)].copy()
    if selected != "전체":
        candidates = candidates.loc[candidates["법정동명"].eq(selected)]

    coordinates = stations[["id", "x_pos", "y_pos"]].rename(
        columns={"id": "0대_대여소_ID", "x_pos": "위도", "y_pos": "경도"}
    )
    candidates = candidates.merge(
        coordinates, on="0대_대여소_ID", how="left", validate="one_to_one"
    ).sort_values(distance, ascending=False)

    if candidates.empty:
        st.info("선택한 동에서 거리 기준을 초과한 지점이 없습니다.")
    else:
        st.map(candidates.dropna(subset=["위도", "경도"]),
               latitude="위도", longitude="경도")
        st.dataframe(candidates[[
            "법정동명", "0대_대여소명", "대체_대여소명", distance
        ]], hide_index=True)

with tab2:
    st.subheader("주간 유동인구 대비 대여소가 적은 동")
    metric = "대여소당_주간유동인구_지표"
    top = facility.nlargest(10, metric)

    st.bar_chart(top.set_index("법정동명")[metric])
    st.dataframe(top[["법정동명", "주간_유동인구", "대여소_수", metric]],
                 hide_index=True)
    st.caption("이 지표는 확충 검토 지역을 좁히는 데 사용합니다. 설치 위치는 인접 동의 대여소와 보행 접근성을 함께 확인해야 합니다.")

    with st.expander("대여소 유무를 별도로 확인할 동"):
        st.dataframe(unmatched[["법정동명", "주간_유동인구"]], hide_index=True)