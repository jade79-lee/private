import pytest
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import requests
import re
import sys

@pytest.fixture
def extractor():
    """Returns an instance of GitHubPRDiffExtractor."""
    return GitHubPRDiffExtractor()

def test_parse_pr_url_valid(extractor):
    """Tests that a valid PR URL is parsed correctly."""
    url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid(extractor):
    """Tests that an invalid PR URL raises a ValueError."""
    url = "https://invalid.url"
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url(url)

def test_fetch_diff_success(extractor, requests_mock):
    """Tests that the diff is fetched successfully."""
    owner, repo, pr_number = "owner", "repo", "1"
    diff_url = f"https://github.sec.samsung.net/api/v3/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, text="diff content")
    extractor.set_credentials("fake_token", "https://github.sec.samsung.net/api/v3")
    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == "diff content"

def test_fetch_diff_no_credentials(extractor):
    """Tests that fetching without credentials raises a ValueError."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")

def test_fetch_diff_request_exception(extractor, requests_mock):
    """Tests that a request exception is handled correctly."""
    owner, repo, pr_number = "owner", "repo", "1"
    diff_url = f"https://github.sec.samsung.net/api/v3/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, exc=requests.exceptions.RequestException("API error"))
    extractor.set_credentials("fake_token", "https://github.sec.samsung.net/api/v3")
    with pytest.raises(RuntimeError, match="Diff API 호출 오류: API error"):
        extractor.fetch_diff(owner, repo, pr_number)

def test_generate_markdown(extractor):
    """Tests that the markdown is generated correctly."""
    diff_text = "diff"
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "**PR URL:** https://github.sec.samsung.net/owner/repo/pull/1" in markdown
    assert "**Repository:** owner/repo" in markdown
    assert "**PR Number:** #1" in markdown
    assert "```diff\ndiff\n```" in markdown

def test_save_to_markdown(extractor):
    """Tests that the markdown is saved correctly."""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    with patch("builtins.open", mock_open()) as mocked_file:
        filepath = extractor.save_to_markdown("markdown", pr_url)
        assert re.match(r".*pr_diff_owner_repo_1_.*\.md", filepath)
        mocked_file.assert_called_once()

def test_save_to_markdown_exception(extractor):
    """Tests that a file saving exception is handled correctly."""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    with patch("builtins.open", mock_open()) as mocked_file:
        mocked_file.side_effect = Exception("File error")
        with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: File error"):
            extractor.save_to_markdown("markdown", pr_url)

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.save_to_markdown')
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.generate_markdown')
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.fetch_diff')
def test_extract_diff(mock_fetch, mock_generate, mock_save, extractor):
    """Tests the entire diff extraction process."""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
    extractor.set_credentials("fake_token", "https://github.sec.samsung.net/api/v3")
    mock_fetch.return_value = "diff"
    mock_generate.return_value = "markdown"
    mock_save.return_value = "filepath"

    result = extractor.extract_diff(pr_url)

    mock_fetch.assert_called_once_with("owner", "repo", "1")
    mock_generate.assert_called_once_with("diff", pr_url)
    mock_save.assert_called_once_with("markdown", pr_url)
    assert result == "filepath"

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(MockExtractor):
    """Tests the main function's success path."""
    instance = MockExtractor.return_value
    instance.extract_diff.return_value = "/path/to/file.md"
    with patch.object(sys, 'argv', ['script_name', 'http://pr.url']):
        main()
        instance.extract_diff.assert_called_once_with('http://pr.url')

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_failure(MockExtractor):
    """Tests the main function's failure path."""
    instance = MockExtractor.return_value
    instance.extract_diff.side_effect = Exception("Test error")
    with patch.object(sys, 'argv', ['script_name', 'http://pr.url']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1

def test_main_no_args():
    """Tests the main function with no arguments."""
    with patch.object(sys, 'argv', ['script_name']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1
