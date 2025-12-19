import pytest
from unittest.mock import patch, mock_open, MagicMock
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import sys
import requests

@pytest.fixture
def extractor():
    """Returns a GitHubPRDiffExtractor instance."""
    return GitHubPRDiffExtractor()

def test_set_credentials(extractor):
    """Tests that the GitHub token and API URL are set correctly."""
    token = "test_token"
    api_url = "https://api.github.com"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == api_url
    assert extractor.headers['Authorization'] == f'token {token}'

def test_parse_pr_url_valid(extractor):
    """Tests parsing a valid PR URL."""
    owner, repo, pr_number = extractor.parse_pr_url("https://github.com/owner/repo/pull/123")
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid(extractor):
    """Tests parsing an invalid PR URL."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("https://github.com/owner/repo/pull/")

@patch('requests.get')
def test_fetch_diff_success(mock_get, extractor):
    """Tests fetching a diff successfully."""
    extractor.set_credentials("test_token", "https://api.github.com")
    mock_response = MagicMock()
    mock_response.text = "diff --git a/file.txt b/file.txt"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    diff = extractor.fetch_diff("owner", "repo", "123")
    assert diff == "diff --git a/file.txt b/file.txt"
    mock_get.assert_called_once_with(
        "https://api.github.com/repos/owner/repo/pulls/123",
        headers=extractor.headers
    )

def test_fetch_diff_no_credentials(extractor):
    """Tests that a ValueError is raised when credentials are not set."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "123")

@patch('requests.get')
def test_fetch_diff_request_exception(mock_get, extractor):
    """Tests that a RuntimeError is raised when a request exception occurs."""
    extractor.set_credentials("test_token", "https://api.github.com")
    mock_get.side_effect = requests.exceptions.RequestException("Test error")
    with pytest.raises(RuntimeError, match="Diff API 호출 오류: Test error"):
        extractor.fetch_diff("owner", "repo", "123")

def test_generate_markdown(extractor):
    """Tests that the markdown is generated correctly."""
    diff_text = "diff --git a/file.txt b/file.txt"
    pr_url = "https://github.com/owner/repo/pull/123"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "# PR Diff" in markdown
    assert f"**PR URL:** {pr_url}" in markdown
    assert "```diff" in markdown
    assert diff_text in markdown

@patch('builtins.open', new_callable=mock_open)
@patch('os.getcwd', return_value="/fake/dir")
def test_save_to_markdown_success(mock_getcwd, mock_open_file, extractor):
    """Tests saving the markdown to a file successfully."""
    markdown_content = "# PR Diff"
    pr_url = "https://github.com/owner/repo/pull/123"
    filepath = extractor.save_to_markdown(markdown_content, pr_url)
    assert filepath.startswith("/fake/dir/pr_diff_owner_repo_123_")
    assert filepath.endswith(".md")
    mock_open_file.assert_called_once_with(filepath, 'w', encoding='utf-8')
    mock_open_file().write.assert_called_once_with(markdown_content)

@patch('builtins.open', side_effect=Exception("Test error"))
@patch('os.getcwd', return_value="/fake/dir")
def test_save_to_markdown_exception(mock_getcwd, mock_open_file, extractor):
    """Tests that a RuntimeError is raised when a file saving error occurs."""
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: Test error"):
        extractor.save_to_markdown("# PR Diff", "https://github.com/owner/repo/pull/123")

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.save_to_markdown')
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.generate_markdown')
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.fetch_diff')
def test_extract_diff_success(mock_fetch, mock_generate, mock_save, extractor):
    """Tests the entire diff extraction process."""
    pr_url = "https://github.com/owner/repo/pull/123"
    mock_fetch.return_value = "diff text"
    mock_generate.return_value = "markdown"
    mock_save.return_value = "/path/to/file.md"

    result_path = extractor.extract_diff(pr_url)
    assert result_path == "/path/to/file.md"
    mock_fetch.assert_called_once_with("owner", "repo", "123")
    mock_generate.assert_called_once_with("diff text", pr_url)
    mock_save.assert_called_once_with("markdown", pr_url)

@patch('sys.argv', ['script.py', 'https://github.com/owner/repo/pull/123'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value="/path/to/file.md")
def test_main_success(mock_extract_diff):
    """Tests the main function with a valid PR URL."""
    main()
    mock_extract_diff.assert_called_once_with('https://github.com/owner/repo/pull/123')

@patch('sys.argv', ['script.py'])
def test_main_no_args(capsys):
    """Tests the main function with no arguments."""
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "사용법" in captured.out

@patch('sys.argv', ['script.py', 'invalid-url'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=ValueError("Invalid URL"))
def test_main_exception(mock_extract_diff, capsys):
    """Tests the main function when an exception is raised."""
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "오류 발생: Invalid URL" in captured.out
