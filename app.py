import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf

# [설정] 페이지 기본
st.set_page_config(page_title="신규배관 경제성 분석 Simulation", layout="wide")

# [함수] 금융 계산 로직
def manual_npv(rate, values):
    return sum(v / ((1 + rate) ** i) for i, v in enumerate(values))

def calculate_simulation(sim_len, sim_inv, sim_contrib, sim_other, sim_vol, sim_rev, sim_cost, 
                          sim_jeon, rate, tax, period, c_maint, c_adm_jeon, c_adm_m):
    
    # 1. 초기 순투자액 (Year 0)
    net_inv = sim_inv - sim_contrib - sim_other
    
    # 2. 비용 및 이익 계산
    unit_margin = (sim_rev - sim_cost) / sim_vol if sim_vol > 0 else 0
    margin_total = sim_rev - sim_cost
    cost_sga = (sim_len * c_maint) + (sim_len * c_adm_m) + (sim_jeon * c_adm_jeon)
    depreciation = sim_inv / period
    
    # 3. 세후 현금흐름 (OCF) 계산
    ebit = margin_total - cost_sga - depreciation
    net_income = ebit * (1 - tax) 
    ocf = net_income + depreciation
    
    # 4. 현금흐름 배열 생성
    flows = [-net_inv] + [ocf] * int(period)
    
    # 5. 지표 산출 및 IRR 사유 판별
    npv_val = manual_npv(rate, flows)
    
    irr_val = None
    irr_reason = ""
    
    if net_inv <= 0:
        irr_reason = "초기 순투자비가 0원 이하(보조금/분담금 과다)로 수익률 산출이 의미가 없음"
    elif ocf <= 0:
        irr_reason = "운영 적자 지속(연간 OCF ≤ 0)으로 투자금 회수 불가"
    else:
        try:
            irr_val = npf.irr(flows)
            if np.isnan(irr_val):
                irr_val = None
                irr_reason = "수학적 해를 찾을 수 없음 (비정상적 현금흐름)"
        except:
            irr_reason = "계산 오류 발생"
    
    # 6. 최소 경제성 만족 판매량 역산
    pvifa = (1 - (1 + rate) ** (-period)) / rate if rate != 0 else period
    target_ocf = net_inv / pvifa if net_inv > 0 else 0
    target_ebit = (target_ocf - depreciation) / (1 - tax)
    target_margin_total = target_ebit + cost_sga + depreciation
    required_vol = target_margin_total / unit_margin if unit_margin > 0 else 0
    
    return {
        "npv": npv_val, "irr": irr_val, "irr_reason": irr_reason, "net_inv": net_inv, 
        "ocf": ocf, "ebit": ebit, "sga": cost_sga, "dep": depreciation,
        "margin": margin_total, "unit_margin": unit_margin, "flows": flows,
        "required_vol": required_vol
    }

# --------------------------------------------------------------------------
# [UI] 좌측 사이드바
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 분석 변수")
    st.subheader("📊 분석 기준")
    rate_pct = st.number_input("할인율 (%)", value=6.15, step=0.01, format="%.2f")
    tax_pct = st.number_input("법인세율+주민세율 (%)", value=20.9, step=0.1, format="%.1f")
    period = st.number_input("분석 및 상각기간 (년)", value=30, step=1)
    
    st.subheader("💰 비용 단가")
    c_maint = st.number_input("유지비 (원/m)", value=8222)
    c_adm_jeon = st.number_input("관리비 (원/전)", value=6209)
    c_adm_m = st.number_input("관리비 (원/m)", value=13605)
    
    RATE = rate_pct / 100
    TAX = tax_pct / 100

# --------------------------------------------------------------------------
# [UI] 메인 화면
# --------------------------------------------------------------------------
st.title("🏗️ 신규배관 경제성 분석 Simulation")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1. 투자 정보")
    sim_len = st.number_input("투자 길이 (m)", value=7000.0)
    sim_inv = st.number_input("총 공사비 (원)", value=7000000000, format="%d")
    sim_contrib = st.number_input("시설 분담금 (원)", value=22048100, format="%d")
    sim_other = st.number_input("기타 이익 (보조금, 원)", value=7000000000, format="%d")
    sim_jeon = st.number_input("공급 전수 (전)", value=2)

with col2:
    st.subheader("2. 수익 정보 (연간)")
    sim_vol = st.number_input("연간 판매량 (MJ)", value=13250280.0)
    sim_rev = st.number_input("연간 판매액 (매출, 원)", value=305103037)
    sim_cost = st.number_input("연간 판매원가 (원)", value=256160477)

st.divider()

if st.button("🚀 경제성 분석 실행", type="primary"):
    res = calculate_simulation(sim_len, sim_inv, sim_contrib, sim_other, sim_vol, sim_rev, sim_cost,
                               sim_jeon, RATE, TAX, period, c_maint, c_adm_jeon, c_adm_m)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("순현재가치 (NPV)", f"{res['npv']:,.0f} 원")
    
    if res['irr'] is None:
        m2.metric("내부수익률 (IRR)", "계산 불가")
        st.error(f"🚩 **불가 사유**: {res['irr_reason']}")
    else:
        m2.metric("내부수익률 (IRR)", f"{res['irr']*100:.2f} %")
    
    m3.metric("할인회수기간 (DPP)", "회수 불가" if res['npv'] < 0 else "회수 가능")

    st.subheader("🧐 NPV 산출 사유 분석")
    st.markdown(f"""
    1. **운영 수익성**: 연간 매출 마진({res['margin']:,.0f}원) 대비 판관비 합계({res['sga']:,.0f}원) 검토 결과
    2. **고정비 부담**: 매년 **{res['dep']:,.0f}원**의 감가상각비 발생
    3. **현금흐름**: 매년 **{res['ocf']:,.0f}원**의 세후 수요개발 기대이익 발생
    """)

    st.divider()
    st.subheader("💡 경제성 확보를 위한 제언")
    if res['npv'] < 0:
        st.error(f"⚠️ 현재 분석 조건으로는 경제성이 부족합니다. (목표 IRR {rate_pct}%)")
        st.info(f"""
        **판매량 분석 결과:**
        - 현재 연간 사용량: **{sim_vol:,.0f} MJ**
        - 경제성 만족 최소 사용량: **{res['required_vol']:,.0f} MJ**
        
        👉 연간 사용량이 **{res['required_vol']:,.0f} MJ**일 경우 최소 경제성 만족(NPV ≥ 0)이 가능합니다.
        """)
    else:
        st.success(f"✅ 현재 연간 사용량({sim_vol:,.0f} MJ)은 경제성 확보 기준({res['required_vol']:,.0f} MJ)을 충족합니다.")

    st.subheader("🔎 세부 계산 근거")
    ca, cb = st.columns(2)
    ca.info(f"**초기 순투자액(Year 0): {res['net_inv']:,.0f} 원**")
    cb.info(f"**세후 수요개발 기대이익(OCF): {res['ocf']:,.0f} 원**")
    st.line_chart(np.cumsum(res['flows']))
