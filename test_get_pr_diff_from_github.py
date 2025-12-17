import pytest
import os
import sys
import requests
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

# 테스트 대상 스크립트
from get_pr_diff_from_github import GitHubPRDiffExtractor, main

# 테스트에 사용할 상수
TEST_PR_URL = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
TEST_OWNER = "GAUDI"
TEST_REPO = "gaudi-fe"
TEST_PR_NUMBER = "8"
TEST_TOKEN = "test_token"
TEST_API_URL = "https://github.sec.samsung.net/api/v3"
TEST_DIFF_TEXT = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"

@pytest.fixture
def mock_env():
    """토큰과 API URL에 대한 환경 변수 모의 처리"""
    with patch.dict(os.environ, {"GITHUB_TOKEN": TEST_TOKEN, "GHE_API_URL": TEST_API_URL}):
        yield

# GitHubPRDiffExtractor 클래스 테스트
def test_initialization_with_args():
    """인수와 함께 초기화 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN, api_base_url=TEST_API_URL + "/")
    assert extractor.git_token == TEST_TOKEN
    assert extractor.git_api_base_url == TEST_API_URL
    assert extractor.headers["Authorization"] == f"token {TEST_TOKEN}"

def test_initialization_with_env(mock_env):
    """환경 변수와 함께 초기화 테스트"""
    extractor = GitHubPRDiffExtractor()
    assert extractor.git_token == TEST_TOKEN
    assert extractor.git_api_base_url == TEST_API_URL

def test_initialization_no_token():
    """토큰 없이 초기화 테스트"""
    with patch.dict(os.environ, clear=True):
        with pytest.raises(ValueError, match="GitHub 토큰이 제공되지 않았거나 GITHUB_TOKEN 환경 변수가 설정되지 않았습니다."):
            GitHubPRDiffExtractor()

def test_parse_pr_url_valid():
    """유효한 PR URL 파싱 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN)
    owner, repo, pr_number = extractor.parse_pr_url(TEST_PR_URL)
    assert owner == TEST_OWNER
    assert repo == TEST_REPO
    assert pr_number == TEST_PR_NUMBER

def test_parse_pr_url_invalid():
    """유효하지 않은 PR URL 파싱 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN)
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid_url")

@patch('requests.get')
def test_fetch_diff_success(mock_get):
    """Diff 가져오기 성공 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN, api_base_url=TEST_API_URL)
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = TEST_DIFF_TEXT
    mock_get.return_value = mock_response

    diff = extractor.fetch_diff(TEST_OWNER, TEST_REPO, TEST_PR_NUMBER)

    expected_url = f"{TEST_API_URL}/repos/{TEST_OWNER}/{TEST_REPO}/pulls/{TEST_PR_NUMBER}"
    mock_get.assert_called_once_with(expected_url, headers=extractor.headers)
    assert diff == TEST_DIFF_TEXT

@patch('requests.get')
def test_fetch_diff_failure(mock_get):
    """Diff 가져오기 실패 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN)
    mock_get.side_effect = requests.exceptions.RequestException("API Error")

    with pytest.raises(RuntimeError, match="Diff API 호출 오류: API Error"):
        extractor.fetch_diff(TEST_OWNER, TEST_REPO, TEST_PR_NUMBER)

def test_generate_markdown():
    """Markdown 생성 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN)
    markdown = extractor.generate_markdown(TEST_DIFF_TEXT, TEST_PR_URL)
    assert f"**PR URL:** {TEST_PR_URL}" in markdown
    assert f"**Repository:** {TEST_OWNER}/{TEST_REPO}" in markdown
    assert f"**PR Number:** #{TEST_PR_NUMBER}" in markdown
    assert "```diff" in markdown
    assert TEST_DIFF_TEXT in markdown
    assert "```" in markdown

@patch("builtins.open", new_callable=mock_open)
@patch("os.path.join")
@patch("get_pr_diff_from_github.datetime")
def test_save_to_markdown_success(mock_datetime, mock_join, mock_file):
    """Markdown 저장 성공 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN)
    mock_now = datetime(2023, 10, 27, 10, 0, 0)
    mock_datetime.now.return_value = mock_now
    timestamp = mock_now.strftime('%Y%m%d_%H%M%S')

    filename = f"pr_diff_{TEST_OWNER}_{TEST_REPO}_{TEST_PR_NUMBER}_{timestamp}.md"
    expected_filepath = f"/current/dir/{filename}"
    mock_join.return_value = expected_filepath

    markdown_content = "## Test Markdown"
    filepath = extractor.save_to_markdown(markdown_content, TEST_PR_URL)

    mock_join.assert_called_once_with(os.getcwd(), filename)
    mock_file.assert_called_once_with(expected_filepath, 'w', encoding='utf-8')
    mock_file().write.assert_called_once_with(markdown_content)
    assert filepath == expected_filepath

@patch("builtins.open", side_effect=IOError("Permission denied"))
def test_save_to_markdown_failure(mock_open):
    """Markdown 저장 실패 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN)
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: Permission denied"):
        extractor.save_to_markdown("some content", TEST_PR_URL)

@patch.object(GitHubPRDiffExtractor, 'fetch_diff', side_effect=RuntimeError("Fetch Error"))
def test_extract_diff_exception_handling(mock_fetch, capsys):
    """extract_diff 예외 처리 테스트"""
    extractor = GitHubPRDiffExtractor(token=TEST_TOKEN)
    result = extractor.extract_diff(TEST_PR_URL)

    assert result is None
    captured = capsys.readouterr()
    assert "오류 발생: Fetch Error" in captured.err

# main 함수 테스트
@patch('sys.argv', ['script.py', TEST_PR_URL])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(MockExtractor, capsys, mock_env):
    """main 함수 성공 테스트"""
    mock_instance = MockExtractor.return_value
    mock_instance.extract_diff.return_value = "path/to/file.md"

    main()

    captured = capsys.readouterr()
    assert "PR Diff 추출이 완료되었습니다." in captured.out

@patch('sys.argv', ['script.py'])
def test_main_no_args(capsys):
    """main 함수 인수 없는 경우 테스트"""
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "사용법:" in captured.err

@patch('sys.argv', ['script.py', TEST_PR_URL])
def test_main_no_token(capsys):
    """main 함수 토큰 없는 경우 테스트"""
    with patch.dict(os.environ, clear=True), pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "오류: GitHub 토큰" in captured.err

@patch('sys.argv', ['script.py', TEST_PR_URL])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_extraction_fails(MockExtractor, capsys, mock_env):
    """main 함수 추출 실패 테스트"""
    mock_instance = MockExtractor.return_value
    mock_instance.extract_diff.return_value = None

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "PR Diff 추출에 실패했습니다." in captured.err
