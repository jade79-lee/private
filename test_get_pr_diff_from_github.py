import pytest
from unittest.mock import patch, mock_open, MagicMock
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import requests
import sys

@pytest.fixture
def extractor():
    """Fixture to create a GitHubPRDiffExtractor instance for tests."""
    return GitHubPRDiffExtractor()

def test_parse_pr_url_valid(extractor):
    """Test parsing a valid PR URL."""
    url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid_url(extractor):
    """Test parsing an invalid PR URL."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid_url")

def test_set_credentials(extractor):
    """Test setting credentials."""
    token = "test_token"
    api_url = "https://api.github.com"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == api_url
    assert extractor.headers['Authorization'] == f'token {token}'

@patch('requests.get')
def test_fetch_diff_success(mock_get, extractor):
    """Test successfully fetching a diff."""
    mock_response = MagicMock()
    mock_response.text = "diff content"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    extractor.set_credentials("test_token", "https://api.github.com")
    diff = extractor.fetch_diff("owner", "repo", "1")
    assert diff == "diff content"

@patch('requests.get')
def test_fetch_diff_http_error(mock_get, extractor):
    """Test fetching a diff with an HTTP error."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.RequestException("HTTP Error")
    mock_get.return_value = mock_response

    extractor.set_credentials("test_token", "https://api.github.com")
    with pytest.raises(RuntimeError, match="Diff API 호출 오류: HTTP Error"):
        extractor.fetch_diff("owner", "repo", "1")

def test_fetch_diff_no_credentials(extractor):
    """Test fetching a diff without credentials."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")

def test_generate_markdown(extractor):
    """Test generating markdown from diff text."""
    diff_text = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt"
    pr_url = "https://github.com/owner/repo/pull/1"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "# PR Diff" in markdown
    assert "owner/repo" in markdown
    assert "#1" in markdown
    assert f"```diff\n{diff_text.rstrip()}\n```" in markdown

@patch('os.getcwd', return_value='/fake/dir')
@patch('builtins.open', new_callable=mock_open)
def test_save_to_markdown(mock_open_file, mock_getcwd, extractor):
    """Test saving markdown to a file."""
    markdown_content = "## Test Markdown"
    pr_url = "https://github.com/owner/repo/pull/1"
    filepath = extractor.save_to_markdown(markdown_content, pr_url)

    mock_open_file.assert_called_once()
    handle = mock_open_file()
    handle.write.assert_called_once_with(markdown_content)

    assert "/fake/dir" in filepath
    assert "pr_diff_owner_repo_1" in filepath
    assert ".md" in filepath

@patch('os.getcwd', return_value='/fake/dir')
@patch('builtins.open', side_effect=IOError("File Error"))
def test_save_to_markdown_file_error(mock_open, mock_getcwd, extractor):
    """Test file saving error."""
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: File Error"):
        extractor.save_to_markdown("content", "https://github.com/owner/repo/pull/1")

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.fetch_diff', return_value="diff text")
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.generate_markdown', return_value="markdown")
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.save_to_markdown', return_value="/path/to/file.md")
def test_extract_diff(mock_save, mock_generate, mock_fetch, extractor):
    """Test the entire diff extraction process."""
    pr_url = "https://github.com/owner/repo/pull/1"
    extractor.set_credentials("test_token", "https://api.github.com")
    result_path = extractor.extract_diff(pr_url)

    mock_fetch.assert_called_once_with("owner", "repo", "1")
    mock_generate.assert_called_once_with("diff text", pr_url)
    mock_save.assert_called_once_with("markdown", pr_url)
    assert result_path == "/path/to/file.md"

@patch('sys.argv', ['script.py'])
@patch('builtins.print')
@patch('sys.exit', side_effect=SystemExit)
def test_main_no_args(mock_exit, mock_print):
    """Test main with no arguments."""
    with pytest.raises(SystemExit):
        main()
    mock_print.assert_any_call("사용법: python get_pr_diff_from_github.py <PR_URL>")
    mock_exit.assert_called_once_with(1)

@patch('sys.argv', ['script.py', 'pr_url'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value='/path/to/file.md')
@patch('builtins.print')
def test_main_success(mock_print, mock_extract_diff):
    """Test main successful execution."""
    main()
    mock_extract_diff.assert_called_once_with('pr_url')
    mock_print.assert_any_call("PR Diff 추출이 완료되었습니다.")

@patch('sys.argv', ['script.py', 'pr_url'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value=None)
@patch('builtins.print')
def test_main_no_result(mock_print, mock_extract_diff):
    """Test main with no result from extractor."""
    main()
    mock_print.assert_any_call("PR Diff 추출에 실패했습니다.")

@patch('sys.argv', ['script.py', 'pr_url'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=Exception("Test Error"))
@patch('builtins.print')
@patch('sys.exit', side_effect=SystemExit)
def test_main_exception(mock_exit, mock_print, mock_extract_diff):
    """Test main with an exception."""
    with pytest.raises(SystemExit):
        main()
    mock_print.assert_any_call("오류 발생: Test Error")
    mock_exit.assert_called_once_with(1)
