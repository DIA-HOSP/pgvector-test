## 1. 가상환경 만들기


- power shell 관리자 권한으로 실행
- 스크립트 권한 부여
    - `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- 가상환경 생성 
    - `python3 -m venv .venv`
- 가상환경 실행
    - `.\.venv\Scripts\Activate.ps1`

## 2. 라이브러리 설치
- `pip install -r requirements.txt`

## 3. 실행 
- `functions-framework --target dia_agent --debug`

* 주소: http://localhost:8080