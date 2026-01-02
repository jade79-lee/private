
import pytest
from unittest.mock import patch, mock_open
import sys
import os
from datetime import datetime
import requests
import requests_mock

from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """Returns an instance of GitHubPRDiffExtractor."""
    return GitHubPRDiffExtractor()

@pytest.fixture
def mock_datetime_now():
    """Fixture to mock datetime.now()"""
    class MockDateTime(datetime):
        @classmethod
        def now(cls):
            return datetime(2024, 1, 1, 12, 0, 0)
    with patch('get_pr_diff_from_github.datetime', MockDateTime):
        yield

def test_set_credentials(extractor):
    """Test setting credentials."""
    token = "test_token"
    api_base_url = "https://api.github.com"
    extractor.set_credentials(token, api_base_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == api_base_url
    assert extractor.headers['Authorization'] == f'token {token}'

def test_parse_pr_url(extractor):
    """Test parsing a valid PR URL."""
    owner, repo, pr_number = extractor.parse_pr_url("https://github.com/owner/repo/pull/123")
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid(extractor):
    """Test parsing an invalid PR URL."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("https://github.com/owner/repo/invalid/123")

def test_fetch_diff_no_credentials(extractor):
    """Test fetch_diff without credentials."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "123")

def test_fetch_diff_success(extractor):
    """Test fetch_diff with a successful API call."""
    extractor.set_credentials("test_token", "https://api.github.com")
    adapter = requests_mock.Adapter()
    adapter.register_uri('GET', 'https://api.github.com/repos/owner/repo/pulls/123', text='diff content')

    session = requests.Session()
    session.mount('mock://', adapter)

    with patch('requests.get', side_effect=lambda url, headers: adapter.send(requests.Request('GET', url, headers=headers).prepare())):
        diff = extractor.fetch_diff("owner", "repo", "123")
        assert diff == "diff content"

def test_fetch_diff_failure(extractor):
    """Test fetch_diff with a failed API call."""
    extractor.set_credentials("test_token", "https://api.github.com")
    adapter = requests_mock.Adapter()
    adapter.register_uri('GET', 'https://api.github.com/repos/owner/repo/pulls/123', status_code=404)

    session = requests.Session()
    session.mount('mock://', adapter)

    with patch('requests.get', side_effect=lambda url, headers: adapter.send(requests.Request('GET', url, headers=headers).prepare())):
        with pytest.raises(RuntimeError):
            extractor.fetch_diff("owner", "repo", "123")

def test_generate_markdown(extractor, mock_datetime_now):
    """Test generating markdown from diff text."""
    diff_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    pr_url = "https://github.com/owner/repo/pull/123"
    markdown = extractor.generate_markdown(diff_text, pr_url)

    assert "# PR Diff" in markdown
    assert "**PR URL:** https://github.com/owner/repo/pull/123" in markdown
    assert "**Repository:** owner/repo" in markdown
    assert "**PR Number:** #123" in markdown
    assert "**추출 시간:** 2024-01-01 12:00:00" in markdown
    assert "```diff\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world\n```" in markdown

def test_save_to_markdown(extractor, mock_datetime_now):
    """Test saving markdown to a file."""
    markdown_content = "test content"
    pr_url = "https://github.com/owner/repo/pull/123"

    with patch("builtins.open", mock_open()) as mock_file:
        filepath = extractor.save_to_markdown(markdown_content, pr_url)
        expected_filename = "pr_diff_owner_repo_123_20240101_120000.md"
        mock_file.assert_called_once_with(os.path.join(os.getcwd(), expected_filename), 'w', encoding='utf-8')
        mock_file().write.assert_called_once_with(markdown_content)
        assert filepath == os.path.join(os.getcwd(), expected_filename)

def test_save_to_markdown_error(extractor, mock_datetime_now):
    """Test error handling when saving markdown to a file."""
    markdown_content = "test content"
    pr_url = "https://github.com/owner/repo/pull/123"

    with patch("builtins.open", mock_open()) as mock_file:
        mock_file.side_effect = IOError("File error")
        with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: File error"):
            extractor.save_to_markdown(markdown_content, pr_url)

def test_extract_diff(extractor, mock_datetime_now):
    """Test the entire diff extraction process."""
    pr_url = "https://github.com/owner/repo/pull/123"
    diff_text = "diff content"

    extractor.set_credentials("test_token", "https://api.github.com")

    with patch.object(extractor, 'fetch_diff', return_value=diff_text) as mock_fetch, \
         patch.object(extractor, 'generate_markdown', return_value="markdown") as mock_generate, \
         patch.object(extractor, 'save_to_markdown', return_value="filepath") as mock_save:

        result_path = extractor.extract_diff(pr_url)

        mock_fetch.assert_called_once_with("owner", "repo", "123")
        mock_generate.assert_called_once_with(diff_text, pr_url)
        mock_save.assert_called_once_with("markdown", pr_url)
        assert result_path == "filepath"

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(MockExtractor):
    """Test the main function with a valid PR URL."""
    instance = MockExtractor.return_value
    instance.extract_diff.return_value = "filepath"

    with patch.object(sys, 'argv', ['script_name', 'https://github.com/owner/repo/pull/123']):
        main()
        instance.extract_diff.assert_called_once_with('https://github.com/owner/repo/pull/123')

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_no_args(MockExtractor, capsys):
    """Test the main function with no arguments."""
    with patch.object(sys, 'argv', ['script_name']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1

    captured = capsys.readouterr()
    assert "사용법" in captured.out

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_exception(MockExtractor, capsys):
    """Test the main function with an exception."""
    instance = MockExtractor.return_value
    instance.extract_diff.side_effect = Exception("Test error")

    with patch.object(sys, 'argv', ['script_name', 'https://github.com/owner/repo/pull/123']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1

    captured = capsys.readouterr()
    assert "오류 발생: Test error" in captured.out

def test_init_without_credentials(extractor):
    """Test that headers are not set when no token is provided."""
    assert 'Authorization' in extractor.headers
    assert 'Bearer' in extractor.headers['Authorization']
    extractor.set_credentials("", "https://api.github.com")
    assert 'Authorization' not in extractor.headers or 'token' not in extractor.headers['Authorization']

@patch.dict(os.environ, {}, clear=True)
def test_main_no_env_vars(capsys):
    """Test main when environment variables are not set."""
    with patch.object(sys, 'argv', ['script_name', 'https://github.com/owner/repo/pull/123']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1
    captured = capsys.readouterr()
    assert "Git token과 API Base URL을 먼저 설정해주세요." in captured.out
