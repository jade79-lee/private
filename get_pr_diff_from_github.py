#!/usr/bin/env python3
"""
GitHub PR Diff 추출 스크립트
PR URL을 입력받아 해당 PR의 Diff(패치)를 Markdown 파일로 저장합니다.
LLM이 분석하기 쉬운 구조로 저장됩니다.
"""

import sys
import os
import re
import requests
from datetime import datetime



class GitHubPRDiffExtractor:
    def __init__(self):
        # 사용자에게 직접 입력하도록 기본값은 비워둠
        self.git_token = None
        self.git_api_base_url = None
        self.headers = {}

    def set_credentials(self, token: str, api_base_url: str):
        """GitHub 토큰과 API Base URL 설정"""
        self.git_token = token
        self.git_api_base_url = api_base_url.rstrip('/')
        if self.git_token:
            self.headers = {
                'Authorization': f'token {self.git_token}',
                'Accept': 'application/vnd.github.v3.diff'
            }

    def parse_pr_url(self, pr_url: str):
        """
        PR URL에서 owner, repo, pr_number 추출
        예: https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8
        """
        pattern = r'https?://[^/]+/([^/]+)/([^/]+)/pull/(\d+)'
        match = re.match(pattern, pr_url)
        if not match:
            raise ValueError("유효하지 않은 PR URL 형식입니다.")
        owner, repo, pr_number = match.groups()
        return owner, repo, pr_number

    def fetch_diff(self, owner: str, repo: str, pr_number: str) -> str:
        """PR Diff(패치) 내용을 가져옵니다."""
        if not self.git_token or not self.git_api_base_url:
            raise ValueError("Git token과 API Base URL을 먼저 설정해주세요.")
        diff_url = f"{self.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        try:
            response = requests.get(diff_url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Diff API 호출 오류: {e}")

    def generate_markdown(self, diff_text: str, pr_url: str) -> str:
        """Diff를 Markdown 형식으로 변환합니다."""
        owner, repo, pr_number = self.parse_pr_url(pr_url)
        header = f"# PR Diff\n\n"
        header += f"**PR URL:** {pr_url}\n"
        header += f"**Repository:** {owner}/{repo}\n"
        header += f"**PR Number:** #{pr_number}\n"
        header += f"**추출 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        header += "---\n\n"
        # Diff를 코드 블록으로 감싸서 LLM이 쉽게 파싱하도록 함
        body = f"```diff\n{diff_text.rstrip()}\n```\n"
        return header + body

    def save_to_markdown(self, markdown_content: str, pr_url: str) -> str:
        """Markdown 파일로 저장하고 파일 경로를 반환합니다."""
        owner, repo, pr_number = self.parse_pr_url(pr_url)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"pr_diff_{owner}_{repo}_{pr_number}_{timestamp}.md"
        filepath = os.path.join(os.getcwd(), filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f"Diff가 '{filepath}' 파일에 저장되었습니다.")
            return filepath
        except Exception as e:
            raise RuntimeError(f"파일 저장 중 오류 발생: {e}")

    def extract_diff(self, pr_url: str) -> str:
        """전체 Diff 추출 프로세스를 실행하고 파일 경로를 반환합니다."""
        print(f"PR URL에서 Diff 추출 시작: {pr_url}")
        owner, repo, pr_number = self.parse_pr_url(pr_url)
        print(f"Repository: {owner}/{repo}, PR: #{pr_number}")

        diff_text = self.fetch_diff(owner, repo, pr_number)
        print(f"Diff 길이: {len(diff_text)} 바이트")

        markdown = self.generate_markdown(diff_text, pr_url)
        return self.save_to_markdown(markdown, pr_url)


def main():
    """메인 엔트리 포인트"""
    if len(sys.argv) != 2:
        print("사용법: python get_pr_diff_from_github.py <PR_URL>")
        print("예시: python get_pr_diff_from_github.py https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8")
        sys.exit(1)

    pr_url = sys.argv[1]

    token = os.environ.get("GITHUB_TOKEN")
    api_url = os.environ.get("GHE_API_URL")

    if not token or not api_url:
        print("환경 변수 GITHUB_TOKEN과 GHE_API_URL을 설정해야 합니다.")
        sys.exit(1)

    extractor = GitHubPRDiffExtractor()
    extractor.set_credentials(token, api_url)

    try:
        result_path = extractor.extract_diff(pr_url)
        if result_path:
            print("PR Diff 추출이 완료되었습니다.")
        else:
            print("PR Diff 추출에 실패했습니다.")
    except Exception as e:
        print(f"오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
