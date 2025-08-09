import os
import sys
import json
import time
import google.generativeai as genai
from github import Github
from github.GithubException import RateLimitExceededException
from typing import List, Dict, Any


class GeminiPRReviewer:
    def __init__(self):
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY')
        self.github_token = os.environ.get('GITHUB_TOKEN')
        self.pr_number = int(os.environ.get('PR_NUMBER', 0))
        
        # 파일 필터링 설정
        self.skip_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', 
                               '.pdf', '.zip', '.tar', '.gz', '.rar',
                               '.exe', '.dll', '.so', '.dylib',
                               '.lock', '.sum', '.mod']
        
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다")
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN이 설정되지 않았습니다")
        if not self.pr_number:
            raise ValueError("PR_NUMBER가 설정되지 않았습니다")
        
        # Initialize Gemini
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        
        # Initialize GitHub
        self.github = Github(self.github_token)
        self.repo = self._get_repository()
        self.pr = self.repo.get_pull(self.pr_number)
    
    def _get_repository(self) -> Any:
        """GitHub 레포지토리 객체 가져오기"""
        # GitHub Actions 환경변수에서 레포지토리 정보 추출
        repo_name = os.environ.get('GITHUB_REPOSITORY')  # owner/repo 형식
        if not repo_name:
            raise ValueError("GITHUB_REPOSITORY가 설정되지 않았습니다")
        return self.github.get_repo(repo_name)
    
    def should_review_file(self, filename: str) -> bool:
        """파일이 리뷰 대상인지 확인"""
        # 확장자 체크만 수행
        for ext in self.skip_extensions:
            if filename.lower().endswith(ext):
                return False
        return True
    
    def get_pr_diff(self) -> Dict[str, Any]:
        """PR의 변경사항 가져오기"""
        files_changed = []
        total_additions = 0
        total_deletions = 0
        skipped_files = []
        
        try:
            # PR의 파일 변경사항 가져오기
            for file in self.pr.get_files():
                # 리뷰 대상이 아닌 파일 스킵
                if not self.should_review_file(file.filename):
                    skipped_files.append(file.filename)
                    continue
                
                # 파일 크기 제한 (너무 큰 파일은 스킵)
                if file.additions + file.deletions > 500:
                    files_changed.append({
                        'filename': file.filename,
                        'status': file.status,
                        'additions': file.additions,
                        'deletions': file.deletions,
                        'patch': f"[파일이 너무 큼: 추가 {file.additions}줄, 삭제 {file.deletions}줄]"
                    })
                else:
                    files_changed.append({
                        'filename': file.filename,
                        'status': file.status,
                        'additions': file.additions,
                        'deletions': file.deletions,
                        'patch': file.patch if hasattr(file, 'patch') and file.patch else ''
                    })
                
                total_additions += file.additions
                total_deletions += file.deletions
                
        except RateLimitExceededException as e:
            print(f"⚠️ GitHub API 한도 초과. 재시도까지 {e.reset_time - time.time():.0f}초 대기 중...")
            time.sleep(max(e.reset_time - time.time() + 1, 60))
            # 재귀 호출로 재시도
            return self.get_pr_diff()
        except Exception as e:
            print(f"❌ PR 정보 가져오기 실패: {str(e)}")
            raise
        
        # 스킵된 파일 정보 출력
        if skipped_files:
            print(f"📝 리뷰 제외 파일 ({len(skipped_files)}개): {', '.join(skipped_files[:5])}" + 
                  (f" 외 {len(skipped_files)-5}개" if len(skipped_files) > 5 else ""))
        
        return {
            'title': self.pr.title,
            'body': self.pr.body or '',
            'files_changed': files_changed,
            'total_additions': total_additions,
            'total_deletions': total_deletions,
            'num_files': len(files_changed),
            'skipped_files': skipped_files
        }
    
    def create_review_prompt(self, pr_info: Dict[str, Any]) -> str:
        """Gemini에게 보낼 리뷰 프롬프트 생성"""
        prompt = f"""
You are an experienced senior developer reviewing code. Focus on providing actionable, constructive feedback.

**PR Title:** {pr_info['title']}
**PR Description:** {pr_info['body']}
**Summary:** {pr_info['num_files']} files changed, +{pr_info['total_additions']} additions, -{pr_info['total_deletions']} deletions

**Changed Files:**
"""
        
        for file in pr_info['files_changed']:
            prompt += f"\n### {file['filename']} ({file['status']})\n"
            prompt += f"Changes: +{file['additions']}, -{file['deletions']}\n"
            if file['patch']:
                prompt += f"```diff\n{file['patch']}\n```\n"
        
        prompt += """

Please provide a thorough code review following this structure:

## 📊 전체 평가
한 단락으로 변경사항의 목적과 영향을 요약

## ✅ 잘한 점
- 코드 품질이나 구현에서 좋은 부분들
- 베스트 프랙티스를 잘 따른 부분

## 🔍 발견된 이슈
각 이슈에 대해:
- **[심각도: 🚨심각/🔴높음/🟡중간/🟢낮음]** 이슈 제목
- 구체적인 문제 설명
- 해결 방법 제안 (코드 예시 포함 가능)

심각도 기준:
- 🚨 **심각(Critical)**: 보안 취약점, 데이터 손실, 시스템 다운 가능성
- 🔴 **높음(High)**: 주요 기능 오류, 성능 심각 저하
- 🟡 **중간(Medium)**: 부분적 기능 오류, 개선 필요
- 🟢 **낮음(Low)**: 코드 스타일, 사소한 개선사항

## 💡 개선 제안
- 성능 최적화 기회
- 코드 가독성 개선
- 리팩토링 제안

## ✨ 추가 고려사항
- 성능 영향

**응답 규칙:**
- 한국어로 작성
- 구체적이고 실행 가능한 피드백 제공
- 이슈가 없으면 "문제없음" 명시
- 코드 예시는 ```언어명 으로 포맷팅
- 리뷰를 받는 사람은 신입 개발자임을 인지하면서 긍정적이고 친절한 톤 유지하되 문제는 명확히 지적
"""
        
        return prompt
    
    def get_gemini_review(self, prompt: str) -> str:
        """Gemini API를 통해 코드 리뷰 받기"""
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"❌ Gemini API 호출 실패: {str(e)}"
    
    def post_review_comment(self, review_content: str):
        """PR에 리뷰 코멘트 게시"""
        comment_body = f"""## 🤖 Gemini AI 코드 리뷰

{review_content}

---
*이 리뷰는 Gemini AI가 자동으로 생성했습니다. 참고용으로만 활용해주세요.*
"""
        
        # PR에 코멘트 추가
        self.pr.create_issue_comment(comment_body)
        print(f"✅ PR #{self.pr_number}에 리뷰가 게시되었습니다")
    
    def run(self):
        """메인 실행 함수"""
        try:
            print(f"📋 PR #{self.pr_number} 정보를 가져오는 중...")
            pr_info = self.get_pr_diff()
            
            # 리뷰할 파일이 없으면 스킵
            if not pr_info['files_changed']:
                print("ℹ️ 리뷰할 파일이 없습니다 (모든 파일이 제외됨)")
                if pr_info['skipped_files']:
                    self.post_review_comment(
                        f"ℹ️ 모든 파일이 리뷰 대상에서 제외되었습니다.\n\n"
                        f"제외된 파일: {', '.join(pr_info['skipped_files'][:10])}"
                        + (f" 외 {len(pr_info['skipped_files'])-10}개" if len(pr_info['skipped_files']) > 10 else "")
                    )
                return
            
            # 변경사항이 너무 크면 스킵
            if pr_info['total_additions'] + pr_info['total_deletions'] > 2000:
                print("⚠️ PR이 자동 리뷰하기에 너무 큽니다")
                self.post_review_comment(
                    "⚠️ 이 PR은 자동 리뷰하기에 너무 큽니다 (2000줄 이상 변경). "
                    "수동 리뷰를 권장합니다."
                )
                return
            
            print("🤖 Gemini에게 리뷰를 요청하는 중...")
            prompt = self.create_review_prompt(pr_info)
            review = self.get_gemini_review(prompt)
            
            print("📝 PR에 리뷰를 게시하는 중...")
            self.post_review_comment(review)
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    reviewer = GeminiPRReviewer()
    reviewer.run()