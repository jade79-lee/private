import pytest
import requests
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
from datetime import datetime
import os
import sys

@pytest.fixture
def extractor():
    """Returns an instance of GitHubPRDiffExtractor."""
    return GitHubPRDiffExtractor()

def test_parse_pr_url(extractor):
    """Tests the parse_pr_url method with a valid PR URL."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid(extractor):
    """Tests the parse_pr_url method with an invalid PR URL."""
    with pytest.raises(ValueError):
        extractor.parse_pr_url("invalid_url")

def test_set_credentials(extractor):
    """Tests the set_credentials method."""
    token = "test_token"
    api_base_url = "https://my.ghe.com/api/v3"
    extractor.set_credentials(token, api_base_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == "https://my.ghe.com/api/v3"
    assert extractor.headers['Authorization'] == f'token {token}'

def test_fetch_diff_success(requests_mock, extractor):
    """Tests the fetch_diff method with a successful API response."""
    extractor.set_credentials("test_token", "https://my.ghe.com/api/v3")
    owner, repo, pr_number = "GAUDI", "gaudi-fe", "8"
    diff_url = f"{extractor.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, text="diff content")
    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == "diff content"

def test_fetch_diff_failure(requests_mock, extractor):
    """Tests the fetch_diff method with a failed API response."""
    extractor.set_credentials("test_token", "https://my.ghe.com/api/v3")
    owner, repo, pr_number = "GAUDI", "gaudi-fe", "8"
    diff_url = f"{extractor.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, status_code=404)
    with pytest.raises(RuntimeError):
        extractor.fetch_diff(owner, repo, pr_number)

def test_fetch_diff_no_credentials(extractor):
    """Tests the fetch_diff method without credentials."""
    with pytest.raises(ValueError):
        extractor.fetch_diff("owner", "repo", "1")

def test_generate_markdown(extractor):
    """Tests the generate_markdown method."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    diff_text = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "# PR Diff" in markdown
    assert f"**PR URL:** {pr_url}" in markdown
    assert "```diff" in markdown
    assert diff_text in markdown

@patch("builtins.open", new_callable=mock_open)
@patch("os.path.join")
@patch("get_pr_diff_from_github.datetime")
def test_save_to_markdown(mock_datetime, mock_path, mock_file, extractor):
    """Tests the save_to_markdown method."""
    mock_now = mock_datetime.now.return_value
    mock_now.strftime.return_value = "20230101_120000"

    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    markdown_content = "# PR Diff"
    timestamp = "20230101_120000"
    filename = f"pr_diff_GAUDI_gaudi-fe_8_{timestamp}.md"
    mock_path.return_value = filename

    filepath = extractor.save_to_markdown(markdown_content, pr_url)

    mock_datetime.now.assert_called_once()
    mock_path.assert_called_once_with(os.getcwd(), filename)
    mock_file.assert_called_once_with(filename, 'w', encoding='utf-8')
    mock_file().write.assert_called_once_with(markdown_content)
    assert filepath == filename

@patch("get_pr_diff_from_github.GitHubPRDiffExtractor.fetch_diff")
@patch("get_pr_diff_from_github.GitHubPRDiffExtractor.save_to_markdown")
def test_extract_diff(mock_save, mock_fetch, extractor):
    """Tests the extract_diff method."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    mock_fetch.return_value = "diff content"
    mock_save.return_value = "path/to/file.md"

    extractor.set_credentials("test_token", "https://my.ghe.com/api/v3")
    filepath = extractor.extract_diff(pr_url)

    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    mock_fetch.assert_called_once_with(owner, repo, pr_number)

    markdown = extractor.generate_markdown("diff content", pr_url)
    mock_save.assert_called_once_with(markdown, pr_url)
    assert filepath == "path/to/file.md"

@patch("builtins.open", side_effect=IOError("File not found"))
def test_save_to_markdown_exception(mock_open, extractor):
    """Tests exception handling in save_to_markdown."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    with pytest.raises(RuntimeError):
        extractor.save_to_markdown("content", pr_url)

@patch("get_pr_diff_from_github.GitHubPRDiffExtractor")
def test_main_success(MockExtractor, capsys):
    """Tests the main function with a successful execution."""
    instance = MockExtractor.return_value
    instance.extract_diff.return_value = "/path/to/diff.md"

    test_args = ["get_pr_diff_from_github.py", "http://some/url"]
    with patch.object(sys, 'argv', test_args):
        main()

    captured = capsys.readouterr()
    assert "PR Diff 추출이 완료되었습니다." in captured.out

@patch("get_pr_diff_from_github.GitHubPRDiffExtractor")
def test_main_failure(MockExtractor, capsys):
    """Tests the main function when extract_diff returns a falsy value."""
    instance = MockExtractor.return_value
    instance.extract_diff.return_value = None

    test_args = ["get_pr_diff_from_github.py", "http://some/url"]
    with patch.object(sys, 'argv', test_args):
        main()

    captured = capsys.readouterr()
    assert "PR Diff 추출에 실패했습니다." in captured.out

@patch("get_pr_diff_from_github.GitHubPRDiffExtractor")
def test_main_exception(MockExtractor, capsys):
    """Tests the main function when an exception occurs."""
    instance = MockExtractor.return_value
    instance.extract_diff.side_effect = Exception("Test error")

    test_args = ["get_pr_diff_from_github.py", "http://some/url"]
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            main()

    captured = capsys.readouterr()
    assert "오류 발생: Test error" in captured.out
    assert e.type == SystemExit
    assert e.value.code == 1

def test_main_invalid_args(capsys):
    """Tests the main function with invalid arguments."""
    test_args = ["get_pr_diff_from_github.py"]
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            main()

    captured = capsys.readouterr()
    assert "사용법" in captured.out
    assert e.type == SystemExit
    assert e.value.code == 1
