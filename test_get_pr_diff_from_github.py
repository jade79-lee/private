import pytest
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import requests
import os
import sys
from datetime import datetime

# Test data
FAKE_TOKEN = "fake_token"
FAKE_API_URL = "https://fake.api.com"
FAKE_PR_URL = "https://github.sec.samsung.net/owner/repo/pull/123"
FAKE_INVALID_PR_URL = "https://github.sec.samsung.net/owner/repo/pull/"
FAKE_DIFF_TEXT = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
FIXED_DATETIME = datetime(2025, 1, 1, 12, 0, 0)
FIXED_TIMESTAMP = FIXED_DATETIME.strftime('%Y%m%d_%H%M%S')

@pytest.fixture
def extractor():
    """Returns an instance of GitHubPRDiffExtractor."""
    return GitHubPRDiffExtractor()

def test_set_credentials(extractor):
    extractor.set_credentials(FAKE_TOKEN, FAKE_API_URL)
    assert extractor.git_token == FAKE_TOKEN
    assert extractor.git_api_base_url == FAKE_API_URL
    assert extractor.headers['Authorization'] == f'token {FAKE_TOKEN}'

def test_parse_pr_url(extractor):
    owner, repo, pr_number = extractor.parse_pr_url(FAKE_PR_URL)
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid(extractor):
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid_url")

@patch('requests.get')
def test_fetch_diff_success(mock_get, extractor):
    extractor.set_credentials(FAKE_TOKEN, FAKE_API_URL)
    mock_get.return_value.raise_for_status = lambda: None
    mock_get.return_value.text = FAKE_DIFF_TEXT

    diff = extractor.fetch_diff("owner", "repo", "123")
    assert diff == FAKE_DIFF_TEXT
    mock_get.assert_called_once_with(
        f"{FAKE_API_URL}/repos/owner/repo/pulls/123",
        headers=extractor.headers
    )

@patch('requests.get')
def test_fetch_diff_failure(mock_get, extractor):
    extractor.set_credentials(FAKE_TOKEN, FAKE_API_URL)
    mock_get.side_effect = requests.exceptions.RequestException("API Error")

    with pytest.raises(RuntimeError, match="Diff API 호출 오류: API Error"):
        extractor.fetch_diff("owner", "repo", "123")

def test_fetch_diff_no_credentials(extractor):
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "123")

@patch('get_pr_diff_from_github.datetime', wraps=datetime)
def test_generate_markdown(mock_datetime, extractor):
    mock_datetime.now.return_value = FIXED_DATETIME
    markdown = extractor.generate_markdown(FAKE_DIFF_TEXT, FAKE_PR_URL)
    assert "# PR Diff" in markdown
    assert f"**PR URL:** {FAKE_PR_URL}" in markdown
    assert f"**추출 시간:** {FIXED_DATETIME.strftime('%Y-%m-%d %H:%M:%S')}" in markdown
    assert "```diff" in markdown
    assert FAKE_DIFF_TEXT in markdown

@patch("builtins.open", new_callable=mock_open)
@patch('get_pr_diff_from_github.datetime', wraps=datetime)
def test_save_to_markdown_success(mock_datetime, mock_file_open, extractor):
    mock_datetime.now.return_value = FIXED_DATETIME
    owner, repo, pr_number = extractor.parse_pr_url(FAKE_PR_URL)
    filename = f"pr_diff_{owner}_{repo}_{pr_number}_{FIXED_TIMESTAMP}.md"
    expected_filepath = os.path.join(os.getcwd(), filename)

    returned_filepath = extractor.save_to_markdown("markdown_content", FAKE_PR_URL)

    mock_file_open.assert_called_once_with(expected_filepath, 'w', encoding='utf-8')
    mock_file_open().write.assert_called_once_with("markdown_content")
    assert returned_filepath == expected_filepath

@patch("builtins.open", new_callable=mock_open)
def test_save_to_markdown_failure(mock_file_open, extractor):
    mock_file_open.side_effect = Exception("File system error")
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: File system error"):
        extractor.save_to_markdown("some markdown", FAKE_PR_URL)

@patch("get_pr_diff_from_github.GitHubPRDiffExtractor.fetch_diff")
@patch("get_pr_diff_from_github.GitHubPRDiffExtractor.save_to_markdown")
def test_extract_diff(mock_save, mock_fetch, extractor):
    extractor.set_credentials(FAKE_TOKEN, FAKE_API_URL)
    mock_fetch.return_value = FAKE_DIFF_TEXT
    mock_save.return_value = "path/to/file.md"

    result_path = extractor.extract_diff(FAKE_PR_URL)

    owner, repo, pr_number = extractor.parse_pr_url(FAKE_PR_URL)
    mock_fetch.assert_called_once_with(owner, repo, pr_number)
    mock_save.assert_called_once()
    assert result_path == "path/to/file.md"

@patch('sys.argv', ['get_pr_diff_from_github.py', FAKE_PR_URL])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff')
def test_main_success(mock_extract_diff, capsys):
    mock_extract_diff.return_value = "path/to/file.md"
    main()
    captured = capsys.readouterr()
    assert "PR Diff 추출이 완료되었습니다." in captured.out

@patch('sys.argv', ['get_pr_diff_from_github.py', FAKE_PR_URL])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff')
def test_main_failure(mock_extract_diff, capsys):
    mock_extract_diff.side_effect = Exception("Test error")
    with pytest.raises(SystemExit) as e:
        main()
    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "오류 발생: Test error" in captured.out

@patch('sys.argv', ['get_pr_diff_from_github.py'])
def test_main_no_args(capsys):
    with pytest.raises(SystemExit) as e:
        main()
    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "사용법:" in captured.out

@patch('sys.argv', ['get_pr_diff_from_github.py', FAKE_PR_URL])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff')
def test_main_extract_diff_returns_none(mock_extract_diff, capsys):
    mock_extract_diff.return_value = None
    main()
    captured = capsys.readouterr()
    assert "PR Diff 추출에 실패했습니다." in captured.out
