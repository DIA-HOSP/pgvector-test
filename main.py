import os
import json
import psycopg2
import functions_framework
from flask import make_response, render_template_string
from google.oauth2 import service_account
import vertexai
from vertexai.language_models import TextEmbeddingModel
from vertexai.generative_models import GenerativeModel

# 1. 인증 정보 로드
KEY_PATH = "./dia-sys.json"
with open(KEY_PATH) as f:
    key_data = json.load(f)

credentials = service_account.Credentials.from_service_account_info(key_data)
project_id = key_data['project_id']

# AlloyDB 접속 정보
DB_CONFIG = {
    "host": "34.64.252.205",
    "port": "5432",
    "database": "postgres",
    "user": "postgres",
    "password": "test",
    "sslmode": "require"
}

# 2. Vertex AI 초기화
vertexai.init(project=project_id, location="asia-northeast3", credentials=credentials)
embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")
gemini_model = GenerativeModel("gemini-2.5-flash")

# 프론트엔드 HTML 템플릿
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DIA Hospital Agent Test</title>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #f5f5f7; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background: white; padding: 30px; border-radius: 12px; shadow: 0 4px 20px rgba(0,0,0,0.1); width: 100%; max-width: 600px; }
        .form-group { margin-bottom: 15px; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid #d2d2d7; border-radius: 8px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #0071e3; color: white; border: none; border-radius: 8px; cursor: pointer; }
        #result-container { margin-top: 25px; padding: 15px; background: #f9f9fb; border-radius: 8px; border: 1px solid #e5e5e5; min-height: 100px; }
        #result-text { white-space: pre-wrap; line-height: 1.6; }
    </style>
</head>
<body>
<div class="container">
    <h2>DIA Agent 리포트 생성기</h2>
    <div class="form-group">
        <label>NCIS 코드</label>
        <input type="text" id="ncis_code" value="9999999">
    </div>
    <div class="form-group">
        <label>질문 입력</label>
        <input type="text" id="query" placeholder="질문을 입력하세요" onkeypress="if(event.keyCode==13) sendRequest()">
    </div>
    <button onclick="sendRequest()">분석 요청</button>
    <div id="result-container">
        <div id="result-text">결과가 여기에 표시됩니다.</div>
    </div>
</div>
<script>
    async function sendRequest() {
        const query = document.getElementById('query').value;
        const ncis_code = document.getElementById('ncis_code').value;
        const resultText = document.getElementById('result-text');
        
        resultText.innerText = '분석 중...';
        
        try {
            // 같은 서버의 /api 경로로 요청을 보냅니다.
            const response = await fetch('/api', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, ncis_code })
            });
            const data = await response.json();
            resultText.innerText = data.response || data.error;
        } catch (e) {
            resultText.innerText = '에러: ' + e.message;
        }
    }
</script>
</body>
</html>
"""

@functions_framework.http
def dia_agent(request):
    # 1. 라우팅 처리: 루트 경로(/) 접속 시 HTML 반환
    if request.path == '/' or request.path == '':
        return render_template_string(HTML_PAGE)

    # 2. API 요청 처리 (/api 또는 기타 경로)
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json; charset=utf-8'
    }

    if request.method == 'OPTIONS':
        return make_response(('', 204, headers))

    request_json = request.get_json(silent=True) or {}
    user_query = request_json.get('query') or request.args.get('query', '')
    ncis_code = request_json.get('ncis_code') or request.args.get('ncis_code', '9999999')

    try:
        # 3. 질문 벡터화
        embeddings = embedding_model.get_embeddings([user_query])
        query_vec = embeddings[0].values

        # 4. 데이터베이스 조회
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 병원 프로필
        cur.execute("SELECT hospital_name, profile_json FROM hospital_profile WHERE ncis_code = %s", (ncis_code,))
        profile_row = cur.fetchone()
        hospital_name = profile_row[0] if profile_row else "DIA Hospital"
        profile_info = profile_row[1] if profile_row else {}

        # 유사도 기반 전략 컨텍스트
        search_query = """
            SELECT title, content FROM hospital_context 
            WHERE ncis_code = %s 
            ORDER BY embedding <=> %s::vector LIMIT 3
        """
        cur.execute(search_query, (ncis_code, query_vec))
        context_text = "\n".join([f"[{r[0]}] {r[1]}" for r in cur.fetchall()])

        # 최신 매출 스냅샷
        cur.execute("""
            SELECT snapshot_period, snapshot_json FROM hospital_snapshot 
            WHERE ncis_code = %s ORDER BY id DESC LIMIT 1
        """, (ncis_code,))
        snapshot_row = cur.fetchone()
        snapshot_period = snapshot_row[0] if snapshot_row else "정보 없음"
        snapshot_json = snapshot_row[1] if snapshot_row else {}

        cur.close()
        conn.close()

        # 5. 프롬프트 구성
        prompt = f"""
        당신은 DIA Hospital의 경영 리포트를 작성하는 수석 전략 컨설턴트입니다. 
        반드시 아래 제공된 [병원 수치 데이터]를 답변의 근거로 사용하십시오.

        [분석 대상]
        병원명: {hospital_name}
        규모: {profile_info.get('beds', '400')}병상

        [병원 수치 데이터]
        기준 시점: {snapshot_period}
        상세 데이터: {json.dumps(snapshot_json, ensure_ascii=False)}
        (※rev는 매출액을 의미하며 단위는 원입니다.)

        [전략 리포트 핵심 내용]
        {context_text}

        답변 지침:
        1. 답변 시작 시 반드시 "{snapshot_period} 기준 소화기내과 매출액 9억 8,000만 원, 정형외과 8억 7,000만 원이 확인되었습니다"와 같이 구체적인 숫자를 언급하십시오.
        2. 숫자를 바탕으로 전략을 제시하십시오.
        3. 추상적인 표현 대신 숫자와 팩트 위주로 답변하십시오.

        원장님 질문: {user_query}
        """

        response = gemini_model.generate_content(prompt)

        result = {
            "response": response.text,
            "ncis_code": ncis_code,
            "hospital_name": hospital_name
        }

        return make_response((json.dumps(result, ensure_ascii=False), 200, headers))

    except Exception as e:
        return make_response((json.dumps({"error": str(e)}, ensure_ascii=False), 500, headers))