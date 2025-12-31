
import sys
import pytest
import requests
import os
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """Returns an instance of GitHubPRDiffExtractor."""
    return GitHubPRDiffExtractor()

@pytest.fixture
def mock_requests(requests_mock):
    """Mocks requests to the GitHub API."""
    return requests_mock

class TestGitHubPRDiffExtractor:

    def test_set_credentials(self, extractor):
        """Tests that credentials are set correctly."""
        token = "test_token"
        api_url = "https://api.github.com"
        extractor.set_credentials(token, api_url)
        assert extractor.git_token == token
        assert extractor.git_api_base_url == api_url
        assert extractor.headers['Authorization'] == f'token {token}'

    @pytest.mark.parametrize("url, expected", [
        ("https://github.com/owner/repo/pull/123", ("owner", "repo", "123")),
        ("http://github.com/owner/repo/pull/456", ("owner", "repo", "456")),
    ])
    def test_parse_pr_url_valid(self, extractor, url, expected):
        """Tests parsing of valid PR URLs."""
        assert extractor.parse_pr_url(url) == expected

    @pytest.mark.parametrize("url", [
        "https://github.com/owner/repo/pull/",
        "https://github.com/owner/repo/123",
        "ftp://github.com/owner/repo/pull/123",
    ])
    def test_parse_pr_url_invalid(self, extractor, url):
        """Tests parsing of invalid PR URLs."""
        with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
            extractor.parse_pr_url(url)

    def test_fetch_diff_success(self, extractor, mock_requests):
        """Tests successful fetching of a PR diff."""
        owner, repo, pr_number = "owner", "repo", "123"
        diff_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        mock_requests.get(diff_url, text="diff content")

        extractor.set_credentials("test_token", "https://api.github.com")
        diff = extractor.fetch_diff(owner, repo, pr_number)
        assert diff == "diff content"

    def test_fetch_diff_no_credentials(self, extractor):
        """Tests that fetching fails without credentials."""
        with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
            extractor.fetch_diff("owner", "repo", "123")

    def test_fetch_diff_http_error(self, extractor, mock_requests):
        """Tests HTTP error during diff fetching."""
        owner, repo, pr_number = "owner", "repo", "123"
        diff_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        mock_requests.get(diff_url, status_code=404)

        extractor.set_credentials("test_token", "https://api.github.com")
        with pytest.raises(RuntimeError, match="Diff API 호출 오류"):
            extractor.fetch_diff(owner, repo, pr_number)

    def test_generate_markdown(self, extractor):
        """Tests Markdown generation."""
        pr_url = "https://github.com/owner/repo/pull/123"
        diff_text = "--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-old\n+new"
        markdown = extractor.generate_markdown(diff_text, pr_url)
        assert "# PR Diff" in markdown
        assert f"**PR URL:** {pr_url}" in markdown
        assert "```diff" in markdown
        assert diff_text in markdown

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.getcwd", return_value="/fake/dir")
    def test_save_to_markdown(self, mock_getcwd, mock_file, extractor):
        """Tests saving Markdown to a file."""
        pr_url = "https://github.com/owner/repo/pull/123"
        markdown_content = "# PR Diff"

        filepath = extractor.save_to_markdown(markdown_content, pr_url)

        assert filepath.startswith("/fake/dir/pr_diff_owner_repo_123")
        assert filepath.endswith(".md")
        mock_file.assert_called_once_with(filepath, 'w', encoding='utf-8')
        mock_file().write.assert_called_once_with(markdown_content)

    @patch("builtins.open", side_effect=IOError("Disk full"))
    def test_save_to_markdown_file_error(self, mock_open, extractor):
        """Tests file saving error."""
        pr_url = "https://github.com/owner/repo/pull/123"
        with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생"):
            extractor.save_to_markdown("content", pr_url)

    @patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="diff")
    @patch.object(GitHubPRDiffExtractor, 'generate_markdown', return_value="markdown")
    @patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="/path/to/file.md")
    def test_extract_diff(self, mock_save, mock_generate, mock_fetch, extractor):
        """Tests the main extraction orchestrator method."""
        pr_url = "https://github.com/owner/repo/pull/123"
        extractor.set_credentials("token", "https://api.github.com")

        result_path = extractor.extract_diff(pr_url)

        mock_fetch.assert_called_once_with("owner", "repo", "123")
        mock_generate.assert_called_once_with("diff", pr_url)
        mock_save.assert_called_once_with("markdown", pr_url)
        assert result_path == "/path/to/file.md"

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(MockExtractor):
    """Tests the main function's success path."""
    instance = MockExtractor.return_value
    instance.extract_diff.return_value = "/path/to/diff.md"

    with patch.object(sys, 'argv', ['script.py', 'https://github.com/owner/repo/pull/1']):
        main()

    instance.extract_diff.assert_called_once_with('https://github.com/owner/repo/pull/1')

def test_main_no_args(capsys):
    """Tests the main function with no arguments."""
    with patch.object(sys, 'argv', ['script.py']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

    captured = capsys.readouterr()
    assert "사용법" in captured.out

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_exception(MockExtractor, capsys):
    """Tests the main function's exception handling."""
    instance = MockExtractor.return_value
    instance.extract_diff.side_effect = Exception("Test error")

    with patch.object(sys, 'argv', ['script.py', 'https://github.com/owner/repo/pull/1']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

    captured = capsys.readouterr()
    assert "오류 발생: Test error" in captured.out
