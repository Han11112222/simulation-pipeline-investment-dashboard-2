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
                         sim_jeon, sim_basic_rev, rate, tax, dep_period, analysis_period, c_maint, c_adm_jeon, c_adm_m):
    
    # 1. 초기 순투자액 (Year 0)
    net_inv = sim_inv - sim_contrib - sim_other
    
    # 2. 고정 수익/비용 항목 계산
    # 총 마진에 '가스판매수익 + 기본요금수익' 반영
    margin_total = (sim_rev - sim_cost) + sim_basic_rev 
    unit_margin = margin_total / sim_vol if sim_vol > 0 else 0
    
    # 판관비 (입력된 단가 기준)
    cost_sga = (sim_len * c_maint) + (sim_len * c_adm_m) + (sim_jeon * c_adm_jeon)
    
    # 연간 감가상각비 (정액법)
    annual_depreciation = sim_inv / dep_period if dep_period > 0 else 0
    
    # 3. 연도별 현금흐름(Flows) 생성 (분석 기간만큼 반복)
    flows = [-net_inv]
    ocfs = []
    
    # 대표값(표시용) - 첫 해 기준
    first_year_ocf = 0
    first_year_ebit = 0
    
    for year in range(1, int(analysis_period) + 1):
        # 감가상각 여부 확인
        if year <= dep_period:
            curr_dep = annual_depreciation
        else:
            curr_dep = 0 # 상각 완료 후
            
        # 영업이익(EBIT)
        ebit = margin_total - cost_sga - curr_dep
        
        # 당기순이익
        net_income = ebit * (1 - tax)
        
        # 영업활동 현금흐름 (OCF)
        ocf = net_income + curr_dep
        
        flows.append(ocf)
        ocfs.append(ocf)
        
        if year == 1:
            first_year_ocf = ocf
            first_year_ebit = ebit

    # 4. 지표 산출
    npv_val = manual_npv(rate, flows)
    
    irr_val = None
    irr_reason = ""
    
    # IRR 예외처리 로직
    if net_inv <= 0:
        irr_reason = "초기 순투자비가 0원 이하(보조금/분담금 과다)로 수익률 산출 의미 없음"
    elif all(f <= 0 for f in ocfs): 
        irr_reason = "운영 적자 지속(모든 연도 OCF ≤ 0)으로 투자금 회수 불가"
    else:
        try:
            irr_val = npf.irr(flows)
        except:
            irr_reason = "계산 오류 발생 (현금흐름 부호 변동 없음 등)"
    
    # 5. 최소 경제성 만족 판매량 역산 (NPV=0 기준)
    pvifa = (1 - (1 + rate) ** (-analysis_period)) / rate if rate != 0 else analysis_period
    target_ocf = net_inv / pvifa if net_inv > 0 else 0
    
    target_ebit = (target_ocf - annual_depreciation) / (1 - tax)
    target_margin_total = target_ebit + cost_sga + annual_depreciation
    required_vol = target_margin_total / unit_margin if unit_margin > 0 else 0
    
    return {
        "npv": npv_val, "irr": irr_val, "irr_reason": irr_reason, "net_inv": net_inv, 
        "first_ocf": first_year_ocf, "first_ebit": first_year_ebit, "sga": cost_sga, 
        "dep": annual_depreciation, "margin": margin_total, "flows": flows, 
        "required_vol": required_vol, "avg_ocf": np.mean(ocfs)
    }

# --------------------------------------------------------------------------
# [UI] 좌측 사이드바
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 분석 변수")
    st.subheader("📊 분석 기준")
    rate_pct = st.number_input("할인율 (%)", value=6.15, step=0.01, format="%.2f")
    tax_pct = st.number_input("법인세율+주민세율 (%)", value=22.0, step=0.1, format="%.1f")
    
    dep_period = st.number_input("감가상각 연수 (년)", value=30, step=1)
    analysis_period = st.number_input("경제성 분석 연수 (년)", value=30, step=1)
    
    st.subheader("💰 비용 단가 (이전 기준값)")
    c_maint = st.number_input("유지비 (원/m)", value=8222, format="%d")
    c_adm_jeon = st.number_input("관리비 (원/전)", value=6209, format="%d")
    c_adm_m = st.number_input("관리비 (원/m)", value=13605, format="%d")
    
    RATE = rate_pct / 100
    TAX = tax_pct / 100

# --------------------------------------------------------------------------
# [UI] 메인 화면
# --------------------------------------------------------------------------
st.title("🏗️ 신규배관 경제성 분석 Simulation")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1. 투자 정보")
    sim_len = st.number_input("투자 길이 (m)", value=0.0, step=1.0)
    sim_inv = st.number_input("총 공사비 (원)", value=0, format="%d")
    sim_contrib = st.number_input("시설 분담금 (원)", value=0, format="%d")
    sim_other = st.number_input("기타 이익 (보조금, 원)", value=0, format="%d")
    sim_jeon = st.number_input("공급 전수 (전)", value=0)

with col2:
    st.subheader("2. 수익 정보 (연간)")
    
    # ✅ [수정] 용도 선택 드롭다운 추가
    usage_type = st.selectbox(
        "가스 용도 선택", 
        ["주택용 (공동주택/단독주택 등)", "기타 (업무용/산업용/영업용 등)"]
    )
    
    sim_vol = st.number_input("연간 판매량 (MJ)", value=0.0)
    sim_rev = st.number_input("가스 연간 판매액 (원)", value=0, format="%d")
    sim_cost = st.number_input("가스 연간 판매원가 (원)", value=0, format="%d")
    
    # ✅ [수정] 선택된 용도에 따라 기본요금 자동 적용
    st.markdown("---")
    if usage_type == "주택용 (공동주택/단독주택 등)":
        st.markdown("**🏡 주택용 기본요금 적용 중**")
        sim_basic_price = st.number_input("월 기본요금 단가 (원/전/월)", value=900, step=10, format="%d")
        sim_basic_rev = sim_basic_price * sim_jeon * 12
        st.info(f"계산된 연간 기본요금 수익: **{sim_basic_rev:,.0f} 원**")
    else:
        st.markdown("**🏢 기타 용도 (기본요금 미적용)**")
        sim_basic_rev = 0
        st.info("해당 용도는 세대별 기본요금이 합산되지 않습니다.")

if st.button("🚀 경제성 분석 실행", type="primary"):
    if sim_vol <= 0 or ((sim_rev - sim_cost) + sim_basic_rev) <= 0:
        st.warning("⚠️ 수익 정보(판매량 및 총 매출마진)를 입력해 주세요.")
    else:
        res = calculate_simulation(sim_len, sim_inv, sim_contrib, sim_other, sim_vol, sim_rev, sim_cost, 
                                   sim_jeon, sim_basic_rev, RATE, TAX, dep_period, analysis_period, c_maint, c_adm_jeon, c_adm_m)
        
        st.divider()
        m1, m2, m3 = st.columns(3)
        # ✅ [수정] 결과값 천 단위 콤마 확실하게 적용
        m1.metric("순현재가치 (NPV)", f"{res['npv']:,.0f} 원")
        
        if res['irr'] is None:
            m2.metric("내부수익률 (IRR)", "계산 불가")
            st.error(f"🚩 **불가 사유**: {res['irr_reason']}")
        else:
            m2.metric("내부수익률 (IRR)", f"{res['irr']*100:.2f} %")
        
        dpp_msg = "회수 가능" if res['npv'] > 0 else "회수 불가 (분석기간 내)"
        m3.metric("할인회수기간 (DPP)", dpp_msg)

        st.subheader("🧐 NPV 산출 사유 분석")
        
        period_comment = ""
        if analysis_period > dep_period:
            period_comment = f"(단, {dep_period}년 이후에는 감가상각이 종료되어 세금 부담이 증가함)"
        
        # ✅ [수정] 본문 텍스트 내 금액도 천 단위 콤마 적용
        st.markdown(f"""
        현재 NPV가 **{res['npv']:,.0f}원**으로 산출된 주요 구조는 다음과 같습니다:
        1. **운영 수익성**: 연간 총 마진({res['margin']:,.0f}원, *기본요금 수익 포함*) 대비 판관비 합계({res['sga']:,.0f}원) 차감
        2. **고정비 부담**: 매년 **{res['dep']:,.0f}원**의 감가상각비 발생 ({dep_period}년간)
        3. **현금흐름**: 첫 해 기준 **{res['first_ocf']:,.0f}원**의 세후 수요개발 기대이익(OCF) 발생 {period_comment}
        4. **미래 가치 누적**: 총 **{analysis_period}년** 간의 현금흐름이 할인율 **{rate_pct}%**로 할인되어 반영됨
        """)

        st.divider()
        st.subheader("💡 경제성 확보를 위한 제언")
        if res['npv'] < 0:
            st.error(f"⚠️ 현재 분석 조건으로는 경제성이 부족합니다. (목표 IRR {rate_pct}%)")
            st.info(f"👉 분석 기간({analysis_period}년) 동안 연간 사용량이 **{res['required_vol']:,.0f} MJ** 이상일 경우 NPV ≥ 0 달성이 가능합니다.")
        else:
            st.success(f"✅ 현재 연간 사용량({sim_vol:,.0f} MJ)은 경제성 확보 기준({res['required_vol']:,.0f} MJ)을 충족합니다.")
        
        chart_data = pd.DataFrame({
            "Year": range(0, int(analysis_period) + 1),
            "Cumulative Cash Flow": np.cumsum(res['flows'])
        })
        st.line_chart(chart_data, x="Year", y="Cumulative Cash Flow")
