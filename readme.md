# 코드

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

## 3. dia-sys.json
- 인증정보가 있는 파일이므로 따로 전달
- cloud run 함수안에도 파일 있습니다.
- main.py 와 같은 디렉토리 안에 위치해 주세요

## 4. 실행 
- `functions-framework --target dia_agent --debug`

* 주소: http://localhost:8080

# DB

## DBeaver 에 추가
- db type : postgreSQL 선택 후 PostgreSQL Driver 설치 
- host: 34.64.252.205
- port: 5432
- username: postgres
- test

