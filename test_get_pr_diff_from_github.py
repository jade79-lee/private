
import pytest
from unittest.mock import patch, MagicMock
import os
import sys
from datetime import datetime

# Add the current directory to sys.path to import the script
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """Returns a GitHubPRDiffExtractor instance."""
    return GitHubPRDiffExtractor()

@pytest.fixture
def mock_datetime():
    """Fixture to mock datetime.now()"""
    class MockDateTime(datetime):
        @classmethod
        def now(cls):
            return cls(2024, 1, 1, 12, 0, 0)
    with patch('get_pr_diff_from_github.datetime', MockDateTime):
        yield

VALID_PR_URL = "https://github.sec.samsung.net/owner/repo/pull/123"
INVALID_PR_URL = "https://invalid-url.com"
OWNER = "owner"
REPO = "repo"
PR_NUMBER = "123"
TEST_TOKEN = "test_token"
TEST_API_URL = "https://github.sec.samsung.net/api/v3"

class TestGitHubPRDiffExtractor:
    def test_parse_pr_url_valid(self, extractor):
        """Test parsing a valid PR URL."""
        owner, repo, pr_number = extractor.parse_pr_url(VALID_PR_URL)
        assert owner == OWNER
        assert repo == REPO
        assert pr_number == PR_NUMBER

    def test_parse_pr_url_invalid_format(self, extractor):
        """Test parsing an invalid PR URL."""
        with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
            extractor.parse_pr_url(INVALID_PR_URL)

    def test_set_credentials(self, extractor):
        """Test setting credentials."""
        extractor.set_credentials(TEST_TOKEN, TEST_API_URL)
        assert extractor.git_token == TEST_TOKEN
        assert extractor.git_api_base_url == TEST_API_URL.rstrip('/')
        assert extractor.headers['Authorization'] == f'token {TEST_TOKEN}'

    def test_fetch_diff_no_credentials(self, extractor):
        """Test fetch_diff without credentials."""
        with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
            extractor.fetch_diff(OWNER, REPO, PR_NUMBER)

    def test_fetch_diff_success(self, requests_mock, extractor):
        """Test fetching diff successfully."""
        extractor.set_credentials(TEST_TOKEN, TEST_API_URL)
        diff_url = f"{TEST_API_URL}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}"
        mock_diff_text = "diff --git a/file.py b/file.py"
        requests_mock.get(diff_url, text=mock_diff_text, status_code=200)

        diff_text = extractor.fetch_diff(OWNER, REPO, PR_NUMBER)
        assert diff_text == mock_diff_text

    def test_fetch_diff_api_error(self, requests_mock, extractor):
        """Test API error during diff fetching."""
        extractor.set_credentials(TEST_TOKEN, TEST_API_URL)
        diff_url = f"{TEST_API_URL}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}"
        requests_mock.get(diff_url, status_code=404, reason="Not Found")

        with pytest.raises(RuntimeError, match="Diff API 호출 오류"):
            extractor.fetch_diff(OWNER, REPO, PR_NUMBER)

    def test_generate_markdown(self, extractor, mock_datetime):
        """Test markdown generation."""
        diff_text = "sample diff"
        markdown = extractor.generate_markdown(diff_text, VALID_PR_URL)
        assert f"**PR URL:** {VALID_PR_URL}" in markdown
        assert f"**Repository:** {OWNER}/{REPO}" in markdown
        assert f"**PR Number:** #{PR_NUMBER}" in markdown
        assert "**추출 시간:** 2024-01-01 12:00:00" in markdown
        assert "```diff\nsample diff\n```" in markdown

    def test_save_to_markdown(self, extractor, tmp_path, mock_datetime):
        """Test saving markdown to a file."""
        markdown_content = "test markdown"

        # Change current working directory to tmp_path for the test
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            filepath = extractor.save_to_markdown(markdown_content, VALID_PR_URL)
            expected_filename = "pr_diff_owner_repo_123_20240101_120000.md"
            assert os.path.basename(filepath) == expected_filename
            assert os.path.exists(filepath)
            with open(filepath, 'r', encoding='utf-8') as f:
                assert f.read() == markdown_content
        finally:
            os.chdir(original_cwd) # Restore original CWD

    def test_save_to_markdown_exception(self, extractor):
        """Test exception during file saving."""
        with patch("builtins.open", side_effect=IOError("File error")):
            with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: File error"):
                extractor.save_to_markdown("content", VALID_PR_URL)

    @patch('get_pr_diff_from_github.GitHubPRDiffExtractor.fetch_diff')
    @patch('get_pr_diff_from_github.GitHubPRDiffExtractor.save_to_markdown')
    def test_extract_diff_success(self, mock_save, mock_fetch, extractor):
        """Test the entire diff extraction process successfully."""
        mock_fetch.return_value = "sample diff"
        mock_save.return_value = "path/to/file.md"

        extractor.set_credentials(TEST_TOKEN, TEST_API_URL)
        result_path = extractor.extract_diff(VALID_PR_URL)

        mock_fetch.assert_called_once_with(OWNER, REPO, PR_NUMBER)
        mock_save.assert_called_once()
        assert result_path == "path/to/file.md"

class TestMainFunction:
    @patch('sys.argv', ['get_pr_diff_from_github.py', VALID_PR_URL])
    @patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff')
    @patch.dict(os.environ, {"GITHUB_TOKEN": TEST_TOKEN, "GHE_API_URL": TEST_API_URL})
    def test_main_success(self, mock_extract_diff, capsys):
        """Test main function success path."""
        mock_extract_diff.return_value = "/path/to/diff.md"
        main()
        mock_extract_diff.assert_called_once_with(VALID_PR_URL)
        captured = capsys.readouterr()
        assert "PR Diff 추출이 완료되었습니다." in captured.out

    @patch('sys.argv', ['get_pr_diff_from_github.py'])
    def test_main_invalid_args(self, capsys):
        """Test main function with invalid arguments."""
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1
        captured = capsys.readouterr()
        assert "사용법:" in captured.out

    @patch('sys.argv', ['get_pr_diff_from_github.py', VALID_PR_URL])
    @patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=Exception("Test error"))
    @patch.dict(os.environ, {"GITHUB_TOKEN": TEST_TOKEN, "GHE_API_URL": TEST_API_URL})
    def test_main_exception(self, mock_extract_diff, capsys):
        """Test main function with an exception."""
        with pytest.raises(SystemExit) as e:
            main()

        assert e.type == SystemExit
        assert e.value.code == 1
        captured = capsys.readouterr()
        assert "오류 발생: Test error" in captured.out

    @patch('sys.argv', ['get_pr_diff_from_github.py', VALID_PR_URL])
    @patch.dict(os.environ, {}, clear=True)
    def test_main_missing_env_vars(self, capsys):
        """Test main function with missing environment variables."""
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1
        captured = capsys.readouterr()
        assert "환경 변수 GITHUB_TOKEN과 GHE_API_URL을 설정해야 합니다." in captured.out
