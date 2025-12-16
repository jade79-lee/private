import pytest
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import sys
import requests

# Constants for testing
TEST_TOKEN = "test_token"
TEST_API_URL = "https://fake.github.api/api/v3"
VALID_PR_URL = "https://fake.github.api/owner/repo/pull/1"
INVALID_PR_URL = "https://invalid.url/pull/1"

@pytest.fixture
def extractor():
    """Returns a GitHubPRDiffExtractor instance with credentials."""
    instance = GitHubPRDiffExtractor()
    instance.set_credentials(TEST_TOKEN, TEST_API_URL)
    return instance

def test_set_credentials(extractor):
    """Test setting credentials."""
    assert extractor.git_token == TEST_TOKEN
    assert extractor.git_api_base_url == TEST_API_URL.rstrip('/')
    assert extractor.headers['Authorization'] == f'token {TEST_TOKEN}'

def test_parse_pr_url(extractor):
    """Test parsing a valid PR URL."""
    owner, repo, pr_number = extractor.parse_pr_url(VALID_PR_URL)
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "1"

def test_parse_invalid_pr_url(extractor):
    """Test parsing an invalid PR URL."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url(INVALID_PR_URL)

@patch('requests.get')
def test_fetch_diff_success(mock_get, extractor):
    """Test fetching diff successfully."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "diff --git a/file.txt b/file.txt"
    diff = extractor.fetch_diff("owner", "repo", "1")
    assert diff == "diff --git a/file.txt b/file.txt"
    mock_get.assert_called_once_with(
        f"{TEST_API_URL}/repos/owner/repo/pulls/1",
        headers=extractor.headers
    )

@patch('requests.get')
def test_fetch_diff_failure(mock_get, extractor):
    """Test fetching diff with a request failure."""
    mock_get.side_effect = requests.exceptions.RequestException("API Error")
    with pytest.raises(RuntimeError, match="Diff API 호출 오류: API Error"):
        extractor.fetch_diff("owner", "repo", "1")

def test_generate_markdown(extractor):
    """Test generating markdown from diff text."""
    diff_text = "diff --git a/file.txt b/file.txt"
    markdown = extractor.generate_markdown(diff_text, VALID_PR_URL)
    assert "# PR Diff" in markdown
    assert f"**PR URL:** {VALID_PR_URL}" in markdown
    assert "```diff" in markdown

@patch('builtins.open', new_callable=mock_open)
@patch('os.getcwd', return_value="/fake/dir")
def test_save_to_markdown(mock_getcwd, mock_file, extractor):
    """Test saving markdown to a file."""
    markdown_content = "# PR Diff"
    filepath = extractor.save_to_markdown(markdown_content, VALID_PR_URL)
    assert filepath.startswith("/fake/dir/pr_diff_owner_repo_1_")
    assert filepath.endswith(".md")
    mock_file.assert_called_once_with(filepath, 'w', encoding='utf-8')

@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="diff")
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="/path/to/file.md")
def test_extract_diff(mock_save, mock_fetch, extractor):
    """Test the main extract_diff workflow."""
    filepath = extractor.extract_diff(VALID_PR_URL)
    assert filepath == "/path/to/file.md"
    mock_fetch.assert_called_once()
    mock_save.assert_called_once()

@patch.object(GitHubPRDiffExtractor, 'extract_diff', return_value="/path/to/file.md")
def test_main_success(mock_extract_diff):
    """Test the main function with a valid PR URL."""
    sys.argv = ["get_pr_diff_from_github.py", VALID_PR_URL]
    main()
    mock_extract_diff.assert_called_once_with(VALID_PR_URL)

@patch('sys.exit')
def test_main_no_args(mock_exit):
    """Test the main function with no arguments."""
    sys.argv = ["get_pr_diff_from_github.py"]
    mock_exit.side_effect = SystemExit(1)
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1

@patch.object(GitHubPRDiffExtractor, 'extract_diff', side_effect=Exception("Test Error"))
@patch('sys.exit')
def test_main_exception(mock_exit, mock_extract_diff):
    """Test the main function with an exception."""
    sys.argv = ["get_pr_diff_from_github.py", VALID_PR_URL]
    main()
    mock_exit.assert_called_with(1)

def test_fetch_diff_no_credentials():
    """Test fetching diff without setting credentials."""
    extractor = GitHubPRDiffExtractor()
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")

@patch('builtins.open', side_effect=IOError("Permission denied"))
@patch('os.getcwd', return_value="/fake/dir")
def test_save_to_markdown_io_error(mock_getcwd, mock_open, extractor):
    """Test saving markdown with an I/O error."""
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: Permission denied"):
        extractor.save_to_markdown("# PR Diff", VALID_PR_URL)
