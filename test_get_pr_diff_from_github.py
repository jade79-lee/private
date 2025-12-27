
import pytest
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import os
import re

@pytest.fixture
def extractor():
    """GitHubPRDiffExtractor 인스턴스를 생성하는 Fixture"""
    return GitHubPRDiffExtractor()

def test_set_credentials(extractor):
    """set_credentials가 정상적으로 Git 토큰과 API URL을 설정하는지 테스트"""
    token = "test_token"
    api_url = "https://fake-api.com"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == api_url
    assert extractor.headers['Authorization'] == f'token {token}'

def test_parse_pr_url_valid(extractor):
    """정상적인 PR URL을 파싱하는지 테스트"""
    owner, repo, pr_number = extractor.parse_pr_url("https://github.sec.samsung.net/owner/repo/pull/123")
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid(extractor):
    """잘못된 PR URL 형식에 대해 ValueError를 발생하는지 테스트"""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid_url")

def test_fetch_diff_no_credentials(extractor):
    """인증 정보 없이 API 호출 시 ValueError를 발생하는지 테스트"""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "123")

def test_fetch_diff_success(requests_mock, extractor):
    """API 호출이 성공하고 Diff 텍스트를 반환하는지 테스트"""
    extractor.set_credentials("test_token", "https://fake-api.com")
    requests_mock.get("https://fake-api.com/repos/owner/repo/pulls/123", text="diff_content")
    diff = extractor.fetch_diff("owner", "repo", "123")
    assert diff == "diff_content"

def test_fetch_diff_api_error(requests_mock, extractor):
    """API 호출 실패 시 RuntimeError를 발생하는지 테스트"""
    extractor.set_credentials("test_token", "https://fake-api.com")
    requests_mock.get("https://fake-api.com/repos/owner/repo/pulls/123", status_code=404)
    with pytest.raises(RuntimeError, match="Diff API 호출 오류"):
        extractor.fetch_diff("owner", "repo", "123")

def test_generate_markdown(extractor):
    """Markdown이 올바른 형식으로 생성되는지 테스트"""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/123"
    diff_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert f"**PR URL:** {pr_url}" in markdown
    assert "**Repository:** owner/repo" in markdown
    assert "**PR Number:** #123" in markdown
    assert "```diff" in markdown
    assert diff_text in markdown

@patch("builtins.open", new_callable=mock_open)
@patch("os.path.join", return_value="/fake/path/pr_diff.md")
def test_save_to_markdown_success(mock_join, mock_file, extractor):
    """Markdown 파일 저장에 성공하고 파일 경로를 반환하는지 테스트"""
    filepath = extractor.save_to_markdown("markdown_content", "https://github.sec.samsung.net/owner/repo/pull/123")
    mock_file.assert_called_once_with("/fake/path/pr_diff.md", 'w', encoding='utf-8')
    mock_file().write.assert_called_once_with("markdown_content")
    assert filepath == "/fake/path/pr_diff.md"

@patch("builtins.open", mock_open())
@patch("os.path.join", return_value="/fake/path/pr_diff.md")
def test_save_to_markdown_exception(mock_join, extractor):
    """파일 저장 중 예외 발생 시 RuntimeError를 발생하는지 테스트"""
    with patch('builtins.open', side_effect=IOError("Disk full")):
        with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: Disk full"):
            extractor.save_to_markdown("content", "https://github.sec.samsung.net/owner/repo/pull/123")


@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="diff text")
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="/fake/path.md")
def test_extract_diff(mock_save, mock_fetch, extractor):
    """전체 Diff 추출 프로세스가 정상적으로 실행되는지 테스트"""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/123"
    extractor.set_credentials("test_token", "https://fake-api.com") # Set credentials before calling extract_diff
    result_path = extractor.extract_diff(pr_url)
    mock_fetch.assert_called_once_with("owner", "repo", "123")
    assert result_path == "/fake/path.md"

@patch('sys.argv', ['script_name', 'https://github.sec.samsung.net/owner/repo/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value='/path/to/diff.md')
@patch('builtins.print')
def test_main_success(mock_print, mock_extract_diff):
    """main 함수가 정상적으로 실행되고 완료 메시지를 출력하는지 테스트"""
    main()
    mock_extract_diff.assert_called_once()
    mock_print.assert_any_call("PR Diff 추출이 완료되었습니다.")


@patch('sys.argv', ['script_name'])
@patch('builtins.print')
def test_main_no_args(mock_print):
    """인자 없이 main 함수 실행 시 사용법을 출력하고 종료하는지 테스트"""
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1
    mock_print.assert_any_call("사용법: python get_pr_diff_from_github.py <PR_URL>")


@patch('sys.argv', ['script_name', 'some_url'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=Exception("Test error"))
@patch('builtins.print')
def test_main_exception(mock_print, mock_extract_diff):
    """main 함수 실행 중 예외 발생 시 오류 메시지를 출력하고 종료하는지 테스트"""
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1
    mock_print.assert_any_call("오류 발생: Test error")

@patch.object(GitHubPRDiffExtractor, 'extract_diff', return_value=None)
@patch('sys.argv', ['script_name', 'https://github.sec.samsung.net/owner/repo/pull/1'])
@patch('builtins.print')
def test_main_failure(mock_print, mock_extract_diff):
    """main 함수가 실패 메시지를 출력하는지 테스트"""
    main()
    mock_extract_diff.assert_called_once()
    mock_print.assert_any_call("PR Diff 추출에 실패했습니다.")
