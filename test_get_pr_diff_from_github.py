import pytest
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import sys

@pytest.fixture
def extractor():
    return GitHubPRDiffExtractor()

pr_url = "https://github.sec.samsung.net/owner/repo/pull/1"
owner = "owner"
repo = "repo"
pr_number = "1"
api_base_url = "https://github.sec.samsung.net/api/v3"
token = "test_token"

def test_set_credentials(extractor):
    extractor.set_credentials(token, api_base_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == api_base_url
    assert f"token {token}" in extractor.headers['Authorization']

def test_parse_pr_url_valid(extractor):
    o, r, p = extractor.parse_pr_url(pr_url)
    assert o == owner
    assert r == repo
    assert p == pr_number

def test_parse_pr_url_invalid(extractor):
    with pytest.raises(ValueError):
        extractor.parse_pr_url("invalid_url")

def test_fetch_diff_success(requests_mock, extractor):
    extractor.set_credentials(token, api_base_url)
    diff_url = f"{api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, text='diff_content')
    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == 'diff_content'

def test_fetch_diff_failure(requests_mock, extractor):
    extractor.set_credentials(token, api_base_url)
    diff_url = f"{api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, status_code=404)
    with pytest.raises(RuntimeError):
        extractor.fetch_diff(owner, repo, pr_number)

def test_fetch_diff_no_credentials(extractor):
    with pytest.raises(ValueError):
        extractor.fetch_diff(owner, repo, pr_number)

def test_generate_markdown(extractor):
    diff_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "# PR Diff" in markdown
    assert pr_url in markdown
    assert f"{owner}/{repo}" in markdown
    assert f"#{pr_number}" in markdown
    assert f"```diff\n{diff_text.rstrip()}\n```" in markdown

def test_save_to_markdown(extractor):
    mock_file = mock_open()
    with patch('builtins.open', mock_file):
        filepath = extractor.save_to_markdown("markdown_content", pr_url)
        assert "pr_diff_owner_repo_1" in filepath
        assert ".md" in filepath
        mock_file.assert_called_once()
        mock_file().write.assert_called_once_with("markdown_content")

def test_save_to_markdown_error(extractor):
    with patch('builtins.open', mock_open()) as mock_file:
        mock_file.side_effect = IOError("File error")
        with pytest.raises(RuntimeError):
            extractor.save_to_markdown("markdown_content", pr_url)

def test_extract_diff(requests_mock, extractor):
    extractor.set_credentials(token, api_base_url)
    diff_url = f"{api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, text='diff_content')

    mock_file = mock_open()
    with patch('builtins.open', mock_file):
        filepath = extractor.extract_diff(pr_url)
        assert "pr_diff_owner_repo_1" in filepath
        assert ".md" in filepath

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value="path/to/file.md")
@patch('builtins.print')
def test_main_success(mock_print, mock_extract_diff):
    test_args = ["get_pr_diff_from_github.py", "http://fake.url/pull/1"]
    with patch.object(sys, 'argv', test_args):
        main()
        mock_extract_diff.assert_called_once_with("http://fake.url/pull/1")

@patch('builtins.print')
def test_main_no_args(mock_print):
    test_args = ["get_pr_diff_from_github.py"]
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=Exception("Test Exception"))
@patch('builtins.print')
def test_main_exception(mock_print, mock_extract_diff):
    test_args = ["get_pr_diff_from_github.py", "http://fake.url/pull/1"]
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value=None)
@patch('builtins.print')
def test_main_fail(mock_print, mock_extract_diff):
    test_args = ["get_pr_diff_from_github.py", "http://fake.url/pull/1"]
    with patch.object(sys, 'argv', test_args):
        main()
        mock_extract_diff.assert_called_once_with("http://fake.url/pull/1")
