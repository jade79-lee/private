
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
def valid_pr_url():
    """Returns a valid PR URL."""
    return "https://github.sec.samsung.net/owner/repo/pull/123"

def test_set_credentials(extractor):
    """Tests if credentials are set correctly."""
    token = "test_token"
    api_url = "https://my.github.api/api/v3"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == "https://my.github.api/api/v3"
    assert extractor.headers['Authorization'] == f'token {token}'

def test_parse_pr_url_valid(extractor, valid_pr_url):
    """Tests parsing of a valid PR URL."""
    owner, repo, pr_number = extractor.parse_pr_url(valid_pr_url)
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid(extractor):
    """Tests parsing of an invalid PR URL."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid_url")

def test_fetch_diff_success(extractor, valid_pr_url):
    """Tests successful fetching of a diff."""
    owner, repo, pr_number = extractor.parse_pr_url(valid_pr_url)
    diff_url = f"https://my.github.api/api/v3/repos/{owner}/{repo}/pulls/{pr_number}"
    diff_text = "diff --git a/file.py b/file.py"

    with requests_mock.Mocker() as m:
        m.get(diff_url, text=diff_text)
        extractor.set_credentials("test_token", "https://my.github.api/api/v3")
        result = extractor.fetch_diff(owner, repo, pr_number)
        assert result == diff_text

def test_fetch_diff_no_credentials(extractor):
    """Tests that a ValueError is raised if credentials are not set."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "123")

def test_fetch_diff_api_error(extractor, valid_pr_url):
    """Tests handling of an API error during diff fetching."""
    owner, repo, pr_number = extractor.parse_pr_url(valid_pr_url)
    diff_url = f"https://my.github.api/api/v3/repos/{owner}/{repo}/pulls/{pr_number}"

    with requests_mock.Mocker() as m:
        m.get(diff_url, status_code=404)
        extractor.set_credentials("test_token", "https://my.github.api/api/v3")
        with pytest.raises(RuntimeError, match="Diff API 호출 오류"):
            extractor.fetch_diff(owner, repo, pr_number)

def test_generate_markdown(extractor, valid_pr_url):
    """Tests the generation of markdown content."""
    diff_text = "diff --git a/file.py b/file.py"
    markdown = extractor.generate_markdown(diff_text, valid_pr_url)
    assert "# PR Diff" in markdown
    assert f"**PR URL:** {valid_pr_url}" in markdown
    assert "```diff" in markdown
    assert diff_text in markdown

@patch("get_pr_diff_from_github.datetime")
@patch("builtins.open", new_callable=mock_open)
def test_save_to_markdown_success(mock_file, mock_datetime, extractor, valid_pr_url):
    """Tests successful saving of markdown to a file."""
    mock_now = datetime(2023, 10, 27, 10, 0, 0)
    mock_datetime.now.return_value = mock_now

    markdown_content = "## Test Markdown"
    filepath = extractor.save_to_markdown(markdown_content, valid_pr_url)

    mock_file.assert_called_once()
    handle = mock_file()
    handle.write.assert_called_once_with(markdown_content)

    owner, repo, pr_number = extractor.parse_pr_url(valid_pr_url)
    timestamp = mock_now.strftime('%Y%m%d_%H%M%S')
    expected_filename = f"pr_diff_{owner}_{repo}_{pr_number}_{timestamp}.md"
    assert os.path.basename(filepath) == expected_filename

@patch("builtins.open", side_effect=IOError("File error"))
def test_save_to_markdown_error(mock_file, extractor, valid_pr_url):
    """Tests error handling during file saving."""
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생"):
        extractor.save_to_markdown("content", valid_pr_url)

@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="fake diff")
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="fake/path.md")
def test_extract_diff_success(mock_save, mock_fetch, extractor, valid_pr_url):
    """Tests the end-to-end diff extraction process."""
    # Since GITHUB_TOKEN and GHE_API_URL are not set, this will fail without mocks
    # We mock the methods that require them.
    extractor.set_credentials("dummy_token", "https://dummy.api")
    result_path = extractor.extract_diff(valid_pr_url)

    mock_fetch.assert_called_once()
    mock_save.assert_called_once()
    assert result_path == "fake/path.md"

def test_main_success(capsys):
    """Tests the main function with a valid PR URL."""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    with patch.object(sys, 'argv', ['script_name', pr_url]):
        with patch.object(GitHubPRDiffExtractor, 'extract_diff', return_value="fake.md") as mock_extract:
            main()
            mock_extract.assert_called_once_with(pr_url)
            captured = capsys.readouterr()
            assert "PR Diff 추출이 완료되었습니다." in captured.out

def test_main_no_args(capsys):
    """Tests the main function with no arguments."""
    with patch.object(sys, 'argv', ['script_name']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
        captured = capsys.readouterr()
        assert "사용법:" in captured.out

def test_main_exception(capsys):
    """Tests the main function when an exception occurs."""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    error_message = "Test error"
    with patch.object(sys, 'argv', ['script_name', pr_url]):
        with patch.object(GitHubPRDiffExtractor, 'extract_diff', side_effect=Exception(error_message)):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1
            captured = capsys.readouterr()
            assert f"오류 발생: {error_message}" in captured.out
