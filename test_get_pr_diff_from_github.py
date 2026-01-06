import pytest
import requests
import requests_mock
from unittest.mock import patch, mock_open
from datetime import datetime
import os
import sys

# Add the script's directory to the Python path to allow importing the script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """Returns a GitHubPRDiffExtractor instance."""
    return GitHubPRDiffExtractor()

def test_initialization(extractor):
    """Test that the extractor initializes with empty credentials."""
    assert extractor.git_token == ""
    assert extractor.git_api_base_url == "https://github.sec.samsung.net/api/v3"
    assert "Authorization" in extractor.headers
    assert extractor.headers["Authorization"] == "Bearer "

def test_set_credentials(extractor):
    """Test that credentials can be set correctly."""
    token = "test_token"
    api_url = "https://example.com/api/v3/"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == "https://example.com/api/v3"
    assert extractor.headers["Authorization"] == f"token {token}"

@pytest.mark.parametrize("url, expected", [
    ("https://github.sec.samsung.net/owner/repo/pull/123", ("owner", "repo", "123")),
    ("http://github.sec.samsung.net/owner/repo/pull/456", ("owner", "repo", "456")),
])
def test_parse_pr_url_valid(extractor, url, expected):
    """Test parsing valid PR URLs."""
    assert extractor.parse_pr_url(url) == expected

@pytest.mark.parametrize("url", [
    "ftp://github.sec.samsung.net/owner/repo/pull/123",
    "https://github.sec.samsung.net/owner/repo/pulls/123", # 'pulls' is invalid
    "https://github.sec.samsung.net/owner/repo/123",
    "not a url"
])
def test_parse_pr_url_invalid(extractor, url):
    """Test parsing invalid PR URLs."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url(url)

def test_fetch_diff_success(extractor, requests_mock):
    """Test fetching a diff successfully."""
    token = "test_token"
    api_url = "https://test.api.com"
    owner, repo, pr_number = "owner", "repo", "1"
    diff_url = f"{api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    expected_diff = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,1 @@\n-hello\n+world"

    extractor.set_credentials(token, api_url)
    requests_mock.get(diff_url, text=expected_diff)

    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == expected_diff

def test_fetch_diff_no_credentials(extractor):
    """Test fetching a diff without setting credentials."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")


def test_fetch_diff_api_error(extractor, requests_mock):
    """Test fetching a diff when the API returns an error."""
    extractor.set_credentials("test_token", "https://test.api.com")
    diff_url = "https://test.api.com/repos/owner/repo/pulls/1"
    requests_mock.get(diff_url, status_code=404, reason="Not Found")

    with pytest.raises(RuntimeError, match="Diff API 호출 오류: 404 Client Error: Not Found for url:"):
        extractor.fetch_diff("owner", "repo", "1")

def test_generate_markdown(extractor):
    """Test the markdown generation."""
    diff_text = "test diff"
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    markdown = extractor.generate_markdown(diff_text, pr_url)

    assert "# PR Diff" in markdown
    assert f"**PR URL:** {pr_url}" in markdown
    assert "**Repository:** owner/repo" in markdown
    assert "**PR Number:** #1" in markdown
    assert "```diff\ntest diff\n```" in markdown

@patch("builtins.open", new_callable=mock_open)
def test_save_to_markdown(mock_file_open, extractor):
    """Test saving markdown to a file."""
    markdown_content = "test markdown"
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"

    with patch("os.getcwd", return_value="/fake/dir"):
        filepath = extractor.save_to_markdown(markdown_content, pr_url)

        # Verify the filename format
        assert filepath.startswith("/fake/dir/pr_diff_owner_repo_1_")
        assert filepath.endswith(".md")

        # Verify the file was written to
        mock_file_open.assert_called_once_with(filepath, 'w', encoding='utf-8')
        handle = mock_file_open()
        handle.write.assert_called_once_with(markdown_content)

def test_save_to_markdown_exception(extractor):
    """Test an exception during file saving."""
    with patch("os.getcwd", return_value="/fake/dir"):
        with patch("builtins.open", side_effect=IOError("Disk full")):
            with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: Disk full"):
                extractor.save_to_markdown("content", "https://github.sec.samsung.net/o/r/pull/1")

def test_extract_diff(extractor, requests_mock):
    """Test the entire diff extraction process."""
    token = "test_token"
    api_url = "https://test.api.com"
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    owner, repo, pr_number = "owner", "repo", "1"
    diff_url = f"{api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    diff_text = "sample diff"

    extractor.set_credentials(token, api_url)
    requests_mock.get(diff_url, text=diff_text)

    with patch.object(extractor, 'save_to_markdown', return_value="path/to/file.md") as mock_save:
        result_path = extractor.extract_diff(pr_url)

        # Verify that save_to_markdown was called with the correct markdown
        mock_save.assert_called_once()
        markdown_arg = mock_save.call_args[0][0]
        assert "```diff\nsample diff\n```" in markdown_arg
        assert result_path == "path/to/file.md"

# --- Tests for the main function ---

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(mock_extractor_class, capsys):
    """Test the main function's success path."""
    # Arrange
    instance = mock_extractor_class.return_value
    instance.extract_diff.return_value = "/path/to/diff.md"
    test_url = "https://github.sec.samsung.net/owner/repo/pull/1"

    with patch.object(sys, 'argv', ['script_name', test_url]):
        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        mock_extractor_class.assert_called_once()
        instance.extract_diff.assert_called_once_with(test_url)
        assert "PR Diff 추출이 완료되었습니다." in captured.out

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_extraction_fails(mock_extractor_class, capsys):
    """Test main when extract_diff returns a falsy value."""
    instance = mock_extractor_class.return_value
    instance.extract_diff.return_value = None  # Simulate failure

    with patch.object(sys, 'argv', ['script_name', 'some_url']):
        main()
        captured = capsys.readouterr()
        assert "PR Diff 추출에 실패했습니다." in captured.out

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_exception(mock_extractor_class, capsys):
    """Test the main function's exception handling."""
    mock_extractor_class.return_value.extract_diff.side_effect = ValueError("Test error")

    with patch.object(sys, 'argv', ['script_name', 'some_url']):
        with pytest.raises(SystemExit) as e:
            main()

            # Assert
            assert e.value.code == 1
            captured = capsys.readouterr()
            assert "오류 발생: Test error" in captured.out

@pytest.mark.parametrize("argv", [
    ['script_name'],  # Not enough arguments
    ['script_name', 'url1', 'url2']  # Too many arguments
])
def test_main_invalid_args(argv, capsys):
    """Test main with invalid command-line arguments."""
    with patch.object(sys, 'argv', argv):
        with pytest.raises(SystemExit) as e:
            main()

            assert e.value.code == 1
            captured = capsys.readouterr()
            assert "사용법:" in captured.out
