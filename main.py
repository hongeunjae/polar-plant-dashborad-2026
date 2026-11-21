import io
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from scipy import stats as sp_stats


def _fmt_id(x):
    """개체번호를 '1', 'A1'처럼 원래 형태로 표시한다."""
    try:
        if pd.isna(x):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        f = float(x)
        return str(int(f)) if f.is_integer() else str(x)
    except (TypeError, ValueError):
        return str(x)


def read_csv(file):
    """인코딩(utf-8-sig -> cp949)을 자동으로 맞춰 CSV를 읽는다."""
    if file is None:
        return pd.DataFrame()
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()


def std_cols(df):
    """학교마다 다른 열 이름을 표준 이름으로 통일한다."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)

    # 숫자 열만 숫자로 변환 (단위·글자가 붙어 있어도 처리)
    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").str.extract(r"(-?\d+\.?\d*)")[0],
                errors="coerce",
            )
            if num.notna().mean() >= 0.5:
                df[c] = num

    # 생중량 열이 없으면 지상부 질량 + 지하부 질량으로 계산
    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]

    # time 열 파싱 (2026-07-15 06:00:00 또는 20260715_0 형식)
    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed
    return df


@st.cache_data
def load_csv(file):
    """CSV를 읽고 열 이름을 표준화한 뒤 반환한다."""
    df = read_csv(file)
    if df is None or df.empty:
        return None
    return std_cols(df)


# ---------------------------------------------------------------------------
# 파일 업로드
# ---------------------------------------------------------------------------
env_file = st.sidebar.file_uploader("환경 CSV", type="csv")
growth_file = st.sidebar.file_uploader("생육 CSV", type="csv")

# 학교명은 업로드한 파일명 앞부분에서 읽기 (하드코딩 금지)
school_name = ""
if env_file is not None:
    school_name = os.path.splitext(os.path.basename(env_file.name))[0]
elif growth_file is not None:
    school_name = os.path.splitext(os.path.basename(growth_file.name))[0]

st.title("그린란드고추냉이의 생육 수준에 따른 뿌리 특성 비교")
st.caption(f"학교: {school_name if school_name else '업로드된 학교 정보를 확인 중...'}")
st.write("가설: 덜 자란 개체일수록 뿌리 질량 대비 길이가 클 것이다.")

with st.spinner("CSV를 읽고 열 이름을 표준화하는 중..."):
    env_df = load_csv(env_file) if env_file is not None else None
    growth_df = load_csv(growth_file) if growth_file is not None else None


# ---------------------------------------------------------------------------
# 사이드바: 생육 측정 항목 선택
# ---------------------------------------------------------------------------
measure_options = ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"]
available_measure = []
if growth_df is not None:
    available_measure = [c for c in measure_options if c in growth_df.columns]
if available_measure:
    selected_measure = st.sidebar.multiselect(
        "생육 측정 항목 선택",
        available_measure,
        default=available_measure,
    )
    if not selected_measure:
        selected_measure = available_measure
else:
    selected_measure = []


# ---------------------------------------------------------------------------
# 데이터 다운로드 (한글 깨짐 방지)
# ---------------------------------------------------------------------------
if growth_df is not None and not growth_df.empty:
    csv_bytes = growth_df.to_csv(index=False).encode("utf-8-sig")
    st.sidebar.download_button(
        "가공된 생육 데이터 내려받기 (UTF-8-SIG)",
        csv_bytes,
        file_name="아라고_생육결과데이터_가공.csv",
        mime="text/csv",
    )


# 스타일 (한글 폰트 깨짐 방지)
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
   font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""",
    unsafe_allow_html=True,
)


tab1, tab2, tab3 = st.tabs(["탐구의 배경", "생육 그룹별 특징 비교", "가설 검증과 최종 결론"])

# ---------------------------------------------------------------------------
# 탭 1. 탐구의 배경
# ---------------------------------------------------------------------------
with tab1:
    try:
        st.subheader("탐구 배경: 같은 환경인데 왜 다르게 자랐을까?")

        if growth_df is None or "생중량" not in growth_df.columns:
            st.info("생육 CSV를 업로드하면 가장 무거운 개체와 가장 가벼운 개체의 생중량을 비교할 수 있어요.")
        else:
            if not pd.api.types.is_numeric_dtype(growth_df["생중량"]):
                st.info("생체중량이 숫자 형식이 아니어서 개체별 생중량을 표시할 수 없어요.")
            else:
                biomass = growth_df["생중량"].dropna()
                if len(biomass) == 0:
                    st.info("생중량 값이 없어 개체별 생중량을 표시할 수 없어요.")
                else:
                    max_v = biomass.max()
                    min_v = biomass.min()

                    st.metric("가장 무거운 개체 생중량", f"{max_v:g} g")
                    st.metric("가장 가벼운 개체 생중량", f"{min_v:g} g")

                    # 개체별 생중량 막대그래프 (최대·최소 강조)
                    tmp = growth_df[["개체번호", "생중량"]].dropna().sort_values("생중량", ascending=True).reset_index(drop=True)
                    tmp["개체 표시"] = tmp["개체번호"].apply(_fmt_id)

                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=tmp["개체 표시"], y=tmp["생중량"], marker_color="#94a3b8", name="개체별 생중량"))
                    fig.add_trace(go.Bar(x=[tmp["개체 표시"].iloc[0]], y=[tmp["생중량"].iloc[0]], marker_color="#ef4444", name="가장 가벼운 개체"))
                    fig.add_trace(go.Bar(x=[tmp["개체 표시"].iloc[-1]], y=[tmp["생중량"].iloc[-1]], marker_color="#f59e0b", name="가장 무거운 개체"))
                    fig.update_layout(title="개체별 생중량", xaxis_title="", yaxis_title="생중량(g)", height=500)
                    st.plotly_chart(fig, width="stretch")

                    # 가장 무거운 개체와 가장 가벼운 개체의 생중량 비교
                    fig2 = go.Figure(data=[go.Bar(x=["가장 무거운 개체", "가장 가벼운 개체"], y=[max_v, min_v], marker_color=["#f59e0b", "#ef4444"])])
                    fig2.update_layout(title="가장 무거운 개체와 가장 가벼운 개체의 생중량 비교", yaxis_title="생중량(g)", height=400)
                    st.plotly_chart(fig2, width="stretch")

                    st.write("**탐구 목적과 가설**")
                    st.write(f"- 탐구 대상: 그린란드고추완이 {len(biomass)}개체")
                    st.write("- 같은 스마트팜에서 같은 기간 재배했지만 개체별 생중량 차이가 발생함")
                    st.write(f"- 가장 무거운 개체: {max_v:g}g / 가장 가벼운 개체: {min_v:g}g")
                    st.write("- 탐구 가설: 덜 자란 개체일수록 뿌리 질량 대비 길이가 클 것이다.")
                    st.write("- 뿌리 질량 대비 길이 = 뿌리 길이 ÷ 뿌리 질량 (mm/g) → 값이 클수록 '질량에 비해 뿌리가 길다'는 뜻")

                    # 환경 데이터 참고 (선택)
                    if env_df is not None and "time" in env_df.columns and "temperature" in env_df.columns:
                        env_plot = env_df.dropna(subset=["time", "temperature"]).set_index("time")["temperature"]
                        env_plot = env_plot.resample("D").mean().dropna()
                        if len(env_plot) > 0:
                            fig3 = go.Figure(data=[go.Scatter(x=env_plot.index, y=env_plot.values, mode="lines", marker_color="#60a5fa")])
                            fig3.update_layout(title="일평균 온도 변화 (환경 참고)", xaxis_title="날짜", yaxis_title="온도(℃)", height=300)
                            st.plotly_chart(fig3, width="stretch")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")


# ---------------------------------------------------------------------------
# 탭 2. 생육 그룹별 특징 비교
# ---------------------------------------------------------------------------
with tab2:
    try:
        st.subheader("생육 그룹별 특징 비교: 덜 자란 개체는 무엇이 달랐을까?")

        if growth_df is None or "생중량" not in growth_df.columns:
            st.info("생육 CSV를 업로드하면 상위 25% 그룹과 하위 25% 그룹의 특징을 비교할 수 있어요.")
        else:
            grp = growth_df.dropna(subset=["생중량"]).copy()
            if not pd.api.types.is_numeric_dtype(grp["생중량"]):
                st.info("생체중량이 숫자 형식이 아니어서 그룹 비교를 할 수 없어요.")
            else:
                if len(grp) < 4:
                    st.info("생중량 값이 4개 미만이어서 그룹을 나누어 비교할 수 없어요.")
                else:
                    q75 = grp["생중량"].quantile(0.75)
                    q25 = grp["생중량"].quantile(0.25)
                    top = grp[grp["생중량"] >= q75]
                    bottom = grp[grp["생중량"] <= q25]

                    # 길이 열 결정 (지하부 길이가 있으면 사용, 없으면 지상부 길이)
                    length_col = None
                    for cand in ("지하부 길이", "지상부 길이"):
                        if cand in growth_df.columns:
                            length_col = cand
                            break

                    # 상위·하위 그룹 요약 표
                    summary_rows = []
                    for m in selected_measure:
                        if m not in grp.columns:
                            continue
                        summary_rows.append({
                            "측정 항목": m,
                            "상위 25% 평균": round(float(top[m].mean()), 2),
                            "하위 25% 평균": round(float(bottom[m].mean()), 2),
                            "차이(상위-하위)": round(float(top[m].mean() - bottom[m].mean()), 2),
                        })
                    if summary_rows:
                        summary_df = pd.DataFrame(summary_rows)
                        st.dataframe(summary_df, width="stretch")

                    # 잎 수 비교
                    if "잎 수" in grp.columns:
                        fig = go.Figure(data=[go.Bar(x=["상위 25% 그룹", "하위 25% 그룹"], y=[top["잎 수"].mean(), bottom["잎 수"].mean()], marker_color=["#3b82f6", "#ef4444"])])
                        fig.update_layout(title="잎 수 비교 (상위 25% vs 하위 25%)", yaxis_title="잎 수(장)", height=400)
                        st.plotly_chart(fig, width="stretch")
                        st.write(f"- 잎 수: 상위 {top['잎 수'].mean():,.1f}장 / 하위 {bottom['잎 수'].mean():,.1f}장")

                    # 뿌리 길이 비교
                    if length_col is not None:
                        fig = go.Figure(data=[go.Bar(x=["상위 25% 그룹", "하위 25% 그룹"], y=[top[length_col].mean(), bottom[length_col].mean()], marker_color=["#3b82f6", "#ef4444"])])
                        fig.update_layout(title=f"뿌리 길이 비교 ({length_col})", yaxis_title="길이(mm)", height=400)
                        st.plotly_chart(fig, width="stretch")
                        st.write(f"- 뿌리 길이: 상위 {top[length_col].mean():,.1f}mm / 하위 {bottom[length_col].mean():,.1f}mm")

                    # 뿌리 질량 비교
                    if "지하부 질량" in grp.columns:
                        fig = go.Figure(data=[go.Bar(x=["상위 25% 그룹", "하위 25% 그룹"], y=[top["지하부 질량"].mean(), bottom["지하부 질량"].mean()], marker_color=["#3b82f6", "#ef4444"])])
                        fig.update_layout(title="뿌리 질량 비교 (상위 25% vs 하위 25%)", yaxis_title="뿌리 질량(g)", height=400)
                        st.plotly_chart(fig, width="stretch")
                        st.write(f"- 뿌리 질량: 상위 {top['지하부 질량'].mean():,.2f}g / 하위 {bottom['지하부 질량'].mean():,.2f}g")

                    st.write("**핵심 내용**")
                    st.write("- 덜 자란 그룹은 잎 수와 뿌리 질량이 적었어요.")
                    st.write("- 뿌리 길이는 두 그룹 사이에 큰 차이가 없었어요.")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")


# ---------------------------------------------------------------------------
# 탭 3. 가설 검증과 최종 결론
# ---------------------------------------------------------------------------
with tab3:
    try:
        st.subheader("가설 검증과 최종 결론: 처음 예상은 맞았을까?")

        if growth_df is None or "생중량" not in growth_df.columns or "지하부 질량" not in growth_df.columns:
            st.info("뿌리 질량 대비 길이 분석과 상관분석을 하려면 생중량·뿌리 질량 열이 있는 생육 CSV가 필요해요.")
        else:
            grp = growth_df.dropna(subset=["생중량", "지하부 질량"]).copy()
            if not pd.api.types.is_numeric_dtype(grp["생중량"]) or not pd.api.types.is_numeric_dtype(grp["지하부 질량"]):
                st.info("생체중량과 뿌리 질량이 숫자 형식이 아니어서 상관분석을 할 수 없어요.")
            else:
                length_col = None
                for cand in ("지하부 길이", "지상부 길이"):
                    if cand in growth_df.columns:
                        length_col = cand
                        break
                if length_col is None:
                    st.info("뿌리 길이 열을 찾을 수 없어 뿌리 질량 대비 길이 분석을 건너뜁니다.")
                else:
                    grp["_ratio"] = grp[length_col] / grp["지하부 질량"]
                    q75 = grp["생중량"].quantile(0.75)
                    top = grp[grp["생중량"] >= q75]
                    bottom = grp[grp["생중량"] <= grp["생중량"].quantile(0.25)]

                    top_ratio = grp.loc[top.index, "_ratio"].mean()
                    bottom_ratio = grp.loc[bottom.index, "_ratio"].mean()

                    st.metric("상위 25% 그룹: 뿌리 질량 대비 길이", f"{top_ratio:.2f} mm/g")
                    st.metric("하위 25% 그룹: 뿌리 질량 대비 길이", f"{bottom_ratio:.2f} mm/g")

                    st.write("**가설:** 덜 자란 개체일수록 뿌리 질량 대비 길이가 클 것이다.")
                    support = "지지됨" if bottom_ratio > top_ratio else "지지되지 않음"
                    st.write(f"- 결과: 하위 그룹({bottom_ratio:.2f} mm/g)이 상위 그룹({top_ratio:.2f} mm/g)보다 약 {bottom_ratio/top_ratio:.1f}배 높았어요. → 가설은 수치상 {support}.")

                    fig = make_subplots(rows=1, cols=2, subplot_titles=("상위 25% vs 하위 25%", "생중량 vs 뿌리 질량 대비 길이"))

                    fig.add_trace(go.Bar(x=["상위 25% 그룹", "하위 25% 그룹"], y=[top_ratio, bottom_ratio], marker_color=["#3b82f6", "#ef4444"]), row=1, col=1)
                    fig.update_yaxes(title_text="뿌리 질량 대비 길이 (mm/g)", row=1, col=1)

                    scatter = grp[["생중량", "_ratio"]].dropna()
                    if len(scatter) >= 2 and scatter["생중량"].nunique() >= 2:
                        slope, intercept = np.polyfit(scatter["생중량"], scatter["_ratio"], 1)
                        trend_x = np.linspace(scatter["생중량"].min(), scatter["생중량"].max(), 100)
                        trend_y = slope * trend_x + intercept

                        fig.add_trace(go.Scatter(x=scatter["생중량"], y=scatter["_ratio"], mode="markers", marker_color="seagreen", name="개체"), row=1, col=2)
                        fig.add_trace(go.Scatter(x=trend_x, y=trend_y, mode="lines", line=dict(color="red", dash="dash"), name="추세선"), row=1, col=2)
                        fig.update_yaxes(title_text="뿌리 질량 대비 길이 (mm/g)", row=1, col=2)
                        fig.update_xaxes(title_text="생중량(g)", row=1, col=2)

                        if len(scatter) >= 3:
                            try:
                                r, _ = sp_stats.pearsonr(scatter["생중량"], scatter["_ratio"])
                                r_txt = f"r = {r:.3f}"
                            except Exception:
                                r = np.corrcoef(scatter["생중량"], scatter["_ratio"])[0, 1]
                                r_txt = f"r = {r:.3f}"
                            st.write(f"**상관계수:** {r_txt} → 생중량이 작을수록 뿌리 질량 대비 길이가 큼 (가설 지지)")
                    else:
                        st.info("산점도를 그릴 데이터(2개 이상)가 부족해요.")

                    st.write("**최종 결론**")
                    st.write("- 덜 자란 개체일수록 뿌리 질량 대비 길이가 크게 나타났어요.")
                    st.write("- 하지만 뿌리가 더 길어서가 아니라 뿌리 질량이 적어서 비율이 커진 것이었어요.")
                    st.write("- 덜 자란 개체의 주요 특징은 상대적으로 적은 잎 수와 뿌리 질량이었어요.")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
