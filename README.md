# deploy-configs

# 🤖 Gemini AI PR 자동 리뷰 시스템

GitHub Pull Request에 대한 자동 코드 리뷰를 제공하는 Gemini AI 기반 시스템입니다.

## 🎯 주요 기능

- **자동 코드 리뷰**: PR이 develop 브랜치로 올라올 때 자동으로 코드 리뷰 실행
- **심각도 분류**: 🚨심각 / 🔴높음 / 🟡중간 / 🟢낮음 4단계로 이슈 분류
- **파일 필터링**: 이미지, 바이너리 등 불필요한 파일 자동 제외
- **Rate Limit 처리**: GitHub API 한도 초과 시 자동 재시도
- **한국어 리뷰**: 신입 개발자도 이해하기 쉬운 한국어 피드백

## 📋 리뷰 구조

Gemini AI는 다음 구조로 리뷰를 제공합니다:

1. 📊 전체 평가: 변경사항 요약
2. ✅ 잘한 점: 좋은 코드 패턴과 구현
3. 🔍 발견된 이슈: 심각도별 문제점과 해결방법
4. 💡 개선 제안: 성능, 가독성 개선 포인트
5. ✨ 추가 고려사항: 테스트, 문서화 등

## 📂 파일 구조

```
DEPLOY-CONFIGS/
└── scripts/
    └── gemini_review.py  # 메인 리뷰 스크립트
```

## ⚙️ 자동 제외 파일

다음 확장자는 자동으로 리뷰에서 제외됩니다:

- 이미지: `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.ico`
- 문서: `.pdf`
- 압축: `.zip`, `.tar`, `.gz`, `.rar`
- 바이너리: `.exe`, `.dll`, `.so`, `.dylib`
- 의존성: `.lock`, `.sum`, `.mod`

## 🚨 제한사항

- **파일당 500줄**: 초과 시 요약만 표시
- **PR당 2000줄**: 초과 시 자동 리뷰 스킵
- **모델**: Gemini 2.5 Pro 사용

## 📊 사용 예시

### 🤖 Gemini AI 코드 리뷰

#### 📊 전체 평가
이 PR은 사용자 인증 시스템과 결제 처리 기능을 추가합니다. 전반적으로 구조는 잘 잡혀있으나 몇 가지 보안 및 성능 개선이 필요합니다.

#### ✅ 잘한 점
- RESTful API 설계 원칙을 잘 따름
- 명확한 변수명과 함수명 사용
- 적절한 try-catch 에러 처리 구현

#### 🔍 발견된 이슈

**[🚨심각] SQL Injection 취약점**
```python
# Line 45 - 취약한 코드
query = f"SELECT * FROM users WHERE id = {user_id}"
```
- 직접 문자열 포맷팅으로 쿼리 생성 시 SQL Injection 위험이 있습니다.
- **해결방법:**
```python
# 안전한 코드
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
```

**[🔴높음] 비밀번호 평문 저장**
```python
# Line 78 - 취약한 코드
user.password = request.form['password']
```
- 비밀번호를 해싱 없이 저장하면 데이터 유출 시 심각한 보안 문제가 발생합니다.
- **해결방법:**
```python
# 안전한 코드
from werkzeug.security import generate_password_hash
user.password = generate_password_hash(request.form['password'])
```

**[🟡중간] API 요청 제한 없음**
```python
# Line 120 - 개선 필요
@app.route('/api/payment', methods=['POST'])
def process_payment():
    # 처리 로직
```
- Rate limiting이 없어 DDoS 공격에 취약합니다.
- **해결방법:**
```python
# 개선된 코드
from flask_limiter import Limiter

@app.route('/api/payment', methods=['POST'])
@limiter.limit("5 per minute")
def process_payment():
    # 처리 로직
```

#### 💡 개선 제안
- Redis를 활용한 캐싱 구현으로 DB 부하 감소
- 입력값 검증 미들웨어 추가 (Joi, Pydantic 등)
- 로깅 시스템 구축 (winston, python logging)

## 🤝 기여하기

개선사항이나 버그를 발견하면 Issue를 생성해주세요!