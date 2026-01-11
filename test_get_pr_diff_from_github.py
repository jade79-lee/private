
import pytest
import requests
import os
from unittest.mock import patch, mock_open
from datetime import datetime

from get_pr_diff_from_github import GitHubPRDiffExtractor

@pytest.fixture
def extractor():
    """GitHubPRDiffExtractor 인스턴스를 생성하고 기본 인증 정보를 설정합니다."""
    ext = GitHubPRDiffExtractor()
    ext.set_credentials("test_token", "https://api.github.com")
    return ext

def test_set_credentials():
    """set_credentials가 토큰, API URL 및 헤더를 올바르게 설정하는지 테스트합니다."""
    extractor = GitHubPRDiffExtractor()
    extractor.set_credentials("my_token", "https://my.api.com/v3")
    assert extractor.git_token == "my_token"
    assert extractor.git_api_base_url == "https://my.api.com/v3"
    assert extractor.headers['Authorization'] == "token my_token"

def test_parse_pr_url_valid():
    """parse_pr_url이 유효한 URL을 올바르게 파싱하는지 테스트합니다."""
    extractor = GitHubPRDiffExtractor()
    url = "https://github.com/owner/repo/pull/123"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid():
    """parse_pr_url이 유효하지 않은 URL에 대해 ValueError를 발생하는지 테스트합니다."""
    extractor = GitHubPRDiffExtractor()
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("https://github.com/owner/repo/invalid/123")

def test_fetch_diff_success(requests_mock, extractor):
    """fetch_diff가 API 호출 성공 시 diff 텍스트를 반환하는지 테스트합니다."""
    owner, repo, pr_number = "owner", "repo", "123"
    diff_url = f"{extractor.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, text="diff content")

    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == "diff content"

def test_fetch_diff_no_credentials():
    """fetch_diff가 인증 정보 없이 호출될 때 ValueError를 발생하는지 테스트합니다."""
    extractor = GitHubPRDiffExtractor()
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "123")

def test_fetch_diff_api_error(requests_mock, extractor):
    """fetch_diff가 API 오류 발생 시 RuntimeError를 발생하는지 테스트합니다."""
    owner, repo, pr_number = "owner", "repo", "123"
    diff_url = f"{extractor.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, status_code=404, reason="Not Found")

    with pytest.raises(RuntimeError, match="Diff API 호출 오류: 404 Client Error: Not Found"):
        extractor.fetch_diff(owner, repo, pr_number)

def test_generate_markdown(extractor):
    """generate_markdown이 올바른 형식의 마크다운을 생성하는지 테스트합니다."""
    pr_url = "https://github.com/owner/repo/pull/123"
    diff_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"

    with patch('get_pr_diff_from_github.datetime') as mock_dt:
        mock_dt.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        markdown = extractor.generate_markdown(diff_text, pr_url)

        assert "# PR Diff" in markdown
        assert f"**PR URL:** {pr_url}" in markdown
        assert "**Repository:** owner/repo" in markdown
        assert "**PR Number:** #123" in markdown
        assert "**추출 시간:** 2023-01-01 12:00:00" in markdown
        assert f"```diff\n{diff_text.rstrip()}\n```" in markdown

@patch("builtins.open", new_callable=mock_open)
def test_save_to_markdown_success(mock_file, extractor):
    """save_to_markdown이 마크다운 파일을 성공적으로 저장하는지 테스트합니다."""
    pr_url = "https://github.com/owner/repo/pull/123"
    markdown_content = "# PR Diff"

    with patch('get_pr_diff_from_github.datetime') as mock_dt:
        mock_dt.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        expected_filename = "pr_diff_owner_repo_123_20230101_120000.md"

        filepath = extractor.save_to_markdown(markdown_content, pr_url)

        mock_file.assert_called_once_with(os.path.join(os.getcwd(), expected_filename), 'w', encoding='utf-8')
        mock_file().write.assert_called_once_with(markdown_content)
        assert filepath == os.path.join(os.getcwd(), expected_filename)

@patch("builtins.open", side_effect=IOError("Disk full"))
def test_save_to_markdown_error(mock_open, extractor):
    """save_to_markdown이 파일 저장 오류 발생 시 RuntimeError를 발생하는지 테스트합니다."""
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: Disk full"):
        extractor.save_to_markdown("content", "https://github.com/owner/repo/pull/1")


@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="diff text")
@patch.object(GitHubPRDiffExtractor, 'generate_markdown', return_value="markdown")
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="path/to/file.md")
def test_extract_diff(mock_save, mock_generate, mock_fetch, extractor):
    """extract_diff가 전체 프로세스를 올바르게 실행하는지 테스트합니다."""
    pr_url = "https://github.com/owner/repo/pull/123"

    result_path = extractor.extract_diff(pr_url)

    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    mock_fetch.assert_called_once_with(owner, repo, pr_number)
    mock_generate.assert_called_once_with("diff text", pr_url)
    mock_save.assert_called_once_with("markdown", pr_url)
    assert result_path == "path/to/file.md"

# main 함수 테스트
from get_pr_diff_from_github import main

@patch('sys.argv', ['script.py'])
def test_main_no_args(capsys):
    """main 함수가 인자 없이 호출될 때 사용법 메시지를 출력하고 종료하는지 테스트합니다."""
    with pytest.raises(SystemExit) as e:
        main()

    captured = capsys.readouterr()
    assert "사용법:" in captured.out
    assert e.value.code == 1

@patch('sys.argv', ['script.py', 'https://github.com/owner/repo/pull/123'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value="path/to/file.md")
def test_main_success(mock_extract, capsys):
    """main 함수가 성공적으로 실행될 때 완료 메시지를 출력하는지 테스트합니다."""
    main()

    captured = capsys.readouterr()
    mock_extract.assert_called_once_with('https://github.com/owner/repo/pull/123')
    assert "PR Diff 추출이 완료되었습니다." in captured.out

@patch('sys.argv', ['script.py', 'https://github.com/owner/repo/pull/123'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value=None)
def test_main_failure_no_result(mock_extract, capsys):
    """main 함수가 결과를 반환하지 못했을 때 실패 메시지를 출력하는지 테스트합니다."""
    main()

    captured = capsys.readouterr()
    mock_extract.assert_called_once_with('https://github.com/owner/repo/pull/123')
    assert "PR Diff 추출에 실패했습니다." in captured.out

@patch('sys.argv', ['script.py', 'https://github.com/owner/repo/pull/123'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=Exception("Test error"))
def test_main_exception(mock_extract, capsys):
    """main 함수에서 예외 발생 시 오류 메시지를 출력하고 종료하는지 테스트합니다."""
    with pytest.raises(SystemExit) as e:
        main()

    captured = capsys.readouterr()
    mock_extract.assert_called_once_with('https://github.com/owner/repo/pull/123')
    assert "오류 발생: Test error" in captured.out
    assert e.value.code == 1
