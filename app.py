# Streamlit 라이브러리를 임포트합니다. 웹 애플리케이션을 구축하는 데 사용됩니다.
import streamlit as st
# Pandas 라이브러리를 임포트합니다. 데이터프레임을 다루는 데 사용됩니다.
import pandas as pd
# Google Gemini API를 사용하기 위한 라이브러리를 임포트합니다.
import google.generativeai as genai

# --- 1. 데이터 로드 및 전처리 ---
# CSV 파일 경로를 정의합니다.
file_path = '행정안전부_착한가격업소 현황_20260331.csv'

try:
    # CSV 파일을 CP949 인코딩으로 읽어 데이터프레임(df)으로 저장합니다.
    df = pd.read_csv(file_path, encoding='cp949')
except UnicodeDecodeError:
    # 인코딩 에러 발생 시 사용자에게 에러 메시지를 표시하고 애플리케이션 실행을 중단합니다.
    st.error("CSV 파일을 불러오는 데 실패했습니다. 인코딩을 확인해주세요. (예: cp949)")
    st.stop() # Streamlit 앱 실행을 중단합니다.

# '가격1' 컬럼을 숫자로 변환합니다. 변환할 수 없는 값은 NaN(결측치)으로 처리합니다.
df['가격1'] = pd.to_numeric(df['가격1'], errors='coerce')
# '시도' 컬럼의 결측치를 '알 수 없음'으로 채웁니다.
df['시도'] = df['시도'].fillna('알 수 없음')
# '시군' 컬럼의 결측치를 '알 수 없음'으로 채웁니다.
df['시군'] = df['시군'].fillna('알 수 없음')
# '업종' 컬럼의 결측치를 '기타'로 채웁니다.
df['업종'] = df['업종'].fillna('기타')
# '메뉴1' 컬럼의 결측치를 '메뉴 정보 없음'으로 채웁니다.
df['메뉴1'] = df['메뉴1'].fillna('메뉴 정보 없음')

# '업종' 컬럼을 요식업 관련 업종으로 필터링합니다.
allowed_업종 = [
    '한식', '중식', '양식', '일식', '분식', '기타외식업', '뷔페', '제과/제빵',
    '패밀리레스토랑', '통닭(치킨)', '호프/통닭', '식육(숯불구이)', '정종/대포집/소주방'
]
df = df[df['업종'].isin(allowed_업종)]

# --- 2. Streamlit UI 구성 ---
# 웹 애플리케이션의 제목을 설정합니다.
st.title('오늘의 모임장소를 찾아볼까요?')
# 애플리케이션 설명 마크다운 텍스트를 추가합니다.
st.markdown("지역과 예산을 선택하면, Gemini AI가 모임 목적에 가장 잘 어울리는 식당을 분석하고 추천해 줍니다.")

# 사이드바를 구성합니다.
st.sidebar.header('🔍 모임 조건 설정') # 사이드바에 모임 조건 설정 섹션 헤더를 추가합니다.

# Streamlit 비밀금고(secrets)에서 Gemini API 키를 가져옵니다.
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except (KeyError, FileNotFoundError):
    api_key = None

# 지역 선택 드롭다운 메뉴를 구성합니다.
# '전체' 옵션을 포함하고, '시도' 컬럼의 고유값들을 정렬하여 리스트로 만듭니다.
selected_sido = st.sidebar.selectbox('시/도 선택', ['전체'] + sorted(df['시도'].unique().tolist()))
if selected_sido == '전체':
    # '시도'가 '전체'일 경우, 모든 '시군' 고유값들을 사용합니다.
    available_sigungu = ['전체'] + sorted(df['시군'].unique().tolist())
else:
    # 특정 '시도'가 선택된 경우, 해당 '시도'에 속하는 '시군' 고유값들만 사용합니다.
    available_sigungu = ['전체'] + sorted(df[df['시도'] == selected_sido]['시군'].unique().tolist())
# '시/군/구' 선택 드롭다운 메뉴를 구성합니다.
selected_sigungu = st.sidebar.selectbox('시/군/구 선택', available_sigungu)

# 1인당 예산을 설정하는 슬라이더를 추가합니다.
per_person_budget = st.sidebar.slider('1인당 예산 (원)', min_value=0, max_value=50000, value=15000, step=1000)
# 인원수를 입력받는 숫자 입력창을 추가합니다.
num_people = st.sidebar.number_input('인원수', min_value=1, max_value=100, value=4, step=1)

# 모임 목적을 선택하는 드롭다운 메뉴 옵션을 정의합니다.
purpose_options = ['데이트', '회식', '가족 모임', '친구 모임', '기타']
# 모임 목적을 선택하는 드롭다운 메뉴를 추가합니다.
selected_purpose = st.sidebar.selectbox('모임 목적', purpose_options)
# 추가 요청사항을 입력받는 텍스트 입력창을 추가합니다.
additional_request = st.sidebar.text_input('추가 요청사항 (예: 조용한 곳, 주차 가능 등)', placeholder="자유롭게 입력하세요")

# --- 3. 1차 데이터 필터링 (Pandas) ---
# 원본 데이터프레임을 복사하여 필터링 작업을 수행합니다.
filtered_df = df.copy()

# '시도'가 '전체'가 아닐 경우, 선택된 '시도'로 데이터프레임을 필터링합니다.
if selected_sido != '전체':
    filtered_df = filtered_df[filtered_df['시도'] == selected_sido]
# '시군'이 '전체'가 아닐 경우, 선택된 '시군'으로 데이터프레임을 필터링합니다.
if selected_sigungu != '전체':
    filtered_df = filtered_df[filtered_df['시군'] == selected_sigungu]

# '가격1' 컬럼에 결측치가 없는 행만 선택합니다.
filtered_df = filtered_df[filtered_df['가격1'].notna()]
# '가격1'이 1인당 예산 이하인 식당만 선택합니다.
filtered_df = filtered_df[filtered_df['가격1'] <= per_person_budget]

# 결과 화면의 헤더를 설정합니다.
st.header('✅ 조건에 맞는 식당 리스트')

if not filtered_df.empty:
    # 사용자에게 보여줄 컬럼 리스트를 정의합니다.
    display_cols = ['업소명', '업종', '메뉴1', '가격1', '주소']
    # 필터링된 데이터프레임을 테이블 형태로 표시합니다. 인덱스는 표시하지 않습니다.
    st.dataframe(filtered_df[display_cols].reset_index(drop=True))

    # 1차 검색된 식당의 총 개수를 표시합니다.
    st.write(f"총 {len(filtered_df)}개의 식당이 1차로 검색되었습니다.")

    # --- 4. 2차 데이터 필터링 및 추천 (Gemini API 연동) ---
    # AI 맞춤 추천 결과 섹션의 헤더를 설정합니다.
    st.header('✨ AI 맞춤 추천 결과')

    # 'Gemini에게 추천받기' 버튼을 생성합니다.
    if st.button('Gemini에게 추천받기 🚀'):
        if not api_key:
            # API 키가 설정되지 않았을 경우 경고 메시지를 표시합니다.
            st.warning("Streamlit Cloud의 Advanced settings -> Secrets에 'GEMINI_API_KEY'를 설정해주세요.")
        else:
            # AI 분석 중임을 알리는 스피너(로딩 인디케이터)를 표시합니다.
            with st.spinner('AI가 모임 목적에 맞는 식당을 분석하고 있습니다...'):
                try:
                    # Gemini API를 설정합니다.
                    genai.configure(api_key=api_key)
                    # 'gemini-2.5-flash' 모델을 로드합니다. (필요시 'gemini-1.5-flash' 사용 가능)
                    model = genai.GenerativeModel('gemini-2.5-flash')

                    # AI에게 전달할 식당 후보 리스트를 텍스트화합니다.
                    # 토큰 사용량 절약을 위해 상위 30개 식당만 전달합니다.
                    candidate_list = filtered_df[display_cols].head(30).to_string(index=False)

                    # 프롬프트 엔지니어링: Gemini AI에게 전달할 상세 요청 내용을 구성합니다.
                    prompt = f"""
                    당신은 센스 있는 맛집 추천 전문가입니다.
                    사용자의 모임 목적은 '{selected_purpose}'입니다.
                    추가 요청사항: '{additional_request}'
                    현재 모임 인원은 {num_people}명 입니다.

                    다음은 사용자의 예산과 지역 조건에 맞는 식당 후보 리스트입니다:
                    {candidate_list}

                    위 리스트 중에서 사용자의 모임 목적에 가장 잘 어울리는 식당 3곳을 선정해 주세요.
                    선정 시, 모임 인원 {num_people}명을 고려하여 적절한 식당을 골라주세요.
                    답변은 다음 양식에 맞춰 작성해 주세요:

                    1. [식당 이름] (업종: ~)
                       - 대표 메뉴 및 가격: ~
                       - 추천 이유: (모임 목적, 업종, 메뉴, 인원수를 연관 지어 이유를 2~3줄로 구체적으로 설명)
                    """

                    # Gemini API를 호출하여 추천 결과를 생성합니다.
                    response = model.generate_content(prompt)

                    # 분석 완료 메시지를 표시합니다.
                    st.success("분석 완료!")
                    # Gemini AI의 추천 결과를 마크다운 형태로 표시합니다.
                    st.markdown(response.text)

                except Exception as e:
                    # API 호출 중 에러 발생 시 에러 메시지를 표시합니다.
                    st.error(f"API 호출 중 에러가 발생했습니다: {e}")
else:
    # 1차 필터링 결과 조건에 맞는 식당이 없을 경우 경고 메시지를 표시합니다.
    st.warning("죄송합니다. 선택하신 조건에 맞는 식당을 찾지 못했습니다. 예산을 올리거나 지역을 넓혀보세요.")
