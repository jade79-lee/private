import pytest
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """Provides a GitHubPRDiffExtractor instance for tests."""
    ext = GitHubPRDiffExtractor()
    # Set dummy credentials for most tests
    ext.set_credentials("dummy_token", "https://api.github.com")
    return ext

def test_parse_pr_url_valid(extractor):
    """Tests parsing a valid GitHub PR URL."""
    url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_http(extractor):
    """Tests parsing a valid HTTP GitHub PR URL."""
    url = "http://github.sec.samsung.net/owner/repo/pull/123"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid_format(extractor):
    """Tests parsing an invalid URL format."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid-url")

def test_parse_pr_url_not_a_pr_url(extractor):
    """Tests parsing a URL that is not a pull request URL."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("https://github.sec.samsung.net/GAUDI/gaudi-fe/issues/8")

def test_generate_markdown(extractor):
    """Tests the generation of markdown content from a diff."""
    diff_text = "diff --git a/file.txt b/file.txt"
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/42"

    now = datetime.now()
    expected_timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

    # Mock datetime to control the timestamp in the output
    class MockDateTime(datetime):
        @classmethod
        def now(cls):
            return now

    import get_pr_diff_from_github
    get_pr_diff_from_github.datetime = MockDateTime

    markdown_content = extractor.generate_markdown(diff_text, pr_url)

    assert "# PR Diff" in markdown_content
    assert f"**PR URL:** {pr_url}" in markdown_content
    assert "**Repository:** owner/repo" in markdown_content
    assert "**PR Number:** #42" in markdown_content
    assert f"**추출 시간:** {expected_timestamp}" in markdown_content
    assert f"```diff\n{diff_text.rstrip()}\n```" in markdown_content

def test_fetch_diff_success(requests_mock, extractor):
    """Tests fetching a diff successfully."""
    owner, repo, pr_number = "owner", "repo", "1"
    diff_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    expected_diff = "diff --git a/test.txt b/test.txt"
    requests_mock.get(diff_url, text=expected_diff)

    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == expected_diff

def test_fetch_diff_no_credentials():
    """Tests that fetching a diff raises an error if credentials are not set."""
    extractor = GitHubPRDiffExtractor() # Create a raw instance
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")

def test_fetch_diff_api_error(requests_mock, extractor):
    """Tests error handling for API failures."""
    owner, repo, pr_number = "owner", "repo", "1"
    diff_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, status_code=404, reason="Not Found")

    with pytest.raises(RuntimeError, match="Diff API 호출 오류:"):
        extractor.fetch_diff(owner, repo, pr_number)

def test_save_to_markdown_success(extractor, tmp_path):
    """Tests saving markdown content to a file successfully."""
    content = "## Test Markdown"
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"

    # Mock os.getcwd to use the temporary directory
    with patch('os.getcwd', return_value=str(tmp_path)):
        filepath = extractor.save_to_markdown(content, pr_url)
        assert os.path.exists(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            assert f.read() == content

def test_save_to_markdown_permission_error(extractor, tmp_path):
    """Tests error handling for file saving failures."""
    content = "## Test"
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"

    # Mock open to raise a permission error
    with patch('builtins.open', side_effect=PermissionError("Permission denied")):
         with patch('os.getcwd', return_value=str(tmp_path)):
            with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생:"):
                extractor.save_to_markdown(content, pr_url)

def test_extract_diff_success(requests_mock, extractor, tmp_path):
    """Tests the entire diff extraction process end-to-end."""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    owner, repo, pr_number = "owner", "repo", "1"
    diff_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    diff_text = "diff --git a/test.txt b/test.txt"
    requests_mock.get(diff_url, text=diff_text)

    with patch('os.getcwd', return_value=str(tmp_path)):
        filepath = extractor.extract_diff(pr_url)
        assert os.path.exists(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "PR Diff" in content
            assert pr_url in content
            assert diff_text in content

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(MockExtractor):
    """Tests the main function's successful execution path."""
    mock_instance = MockExtractor.return_value
    mock_instance.extract_diff.return_value = "/fake/path/pr_diff.md"

    test_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    with patch('sys.argv', ['script_name', test_url]):
        main()

    mock_instance.extract_diff.assert_called_once_with(test_url)

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_extraction_fails(MockExtractor):
    """Tests the main function when the extraction process returns a falsy value."""
    mock_instance = MockExtractor.return_value
    mock_instance.extract_diff.return_value = None # Simulate a failure

    test_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    with patch('sys.argv', ['script_name', test_url]):
        main()

    mock_instance.extract_diff.assert_called_once_with(test_url)

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_exception(MockExtractor):
    """Tests the main function's exception handling."""
    mock_instance = MockExtractor.return_value
    mock_instance.extract_diff.side_effect = ValueError("Test error")

    test_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    with patch('sys.argv', ['script_name', test_url]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

def test_main_invalid_args():
    """Tests the main function with incorrect command-line arguments."""
    with patch('sys.argv', ['script_name']): # No URL provided
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

    with patch('sys.argv', ['script_name', 'url1', 'url2']): # Too many args
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
