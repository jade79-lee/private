
import pytest
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor
import requests
import re

@pytest.fixture
def extractor():
    """Returns an instance of GitHubPRDiffExtractor."""
    return GitHubPRDiffExtractor()

def test_parse_pr_url(extractor):
    """Tests if the PR URL is parsed correctly."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid(extractor):
    """Tests if an invalid PR URL raises a ValueError."""
    pr_url = "https://invalid-url.com"
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url(pr_url)

def test_fetch_diff_success(requests_mock, extractor):
    """Tests a successful diff fetch."""
    extractor.set_credentials("fake_token", "https://github.sec.samsung.net/api/v3")
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    diff_url = f"{extractor.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

    requests_mock.get(diff_url, text="diff content")

    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == "diff content"

def test_fetch_diff_failure(requests_mock, extractor):
    """Tests a failed diff fetch."""
    extractor.set_credentials("fake_token", "https://github.sec.samsung.net/api/v3")
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    diff_url = f"{extractor.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

    requests_mock.get(diff_url, status_code=404)

    with pytest.raises(RuntimeError, match="Diff API 호출 오류:"):
        extractor.fetch_diff(owner, repo, pr_number)

def test_fetch_diff_no_credentials(extractor):
    """Tests fetching a diff without credentials."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")

def test_generate_markdown(extractor):
    """Tests markdown generation."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    diff_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    markdown = extractor.generate_markdown(diff_text, pr_url)

    assert "# PR Diff" in markdown
    assert f"**PR URL:** {pr_url}" in markdown
    assert "**Repository:** GAUDI/gaudi-fe" in markdown
    assert "**PR Number:** #8" in markdown
    assert "```diff" in markdown
    assert diff_text in markdown

@patch("os.path.join", return_value="/fake/path/pr_diff.md")
@patch("builtins.open", new_callable=mock_open)
def test_save_to_markdown_success(mock_file, mock_join, extractor):
    """Tests saving markdown to a file successfully."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    markdown_content = "## Test Markdown"

    filepath = extractor.save_to_markdown(markdown_content, pr_url)

    mock_file.assert_called_once_with("/fake/path/pr_diff.md", 'w', encoding='utf-8')
    mock_file().write.assert_called_once_with(markdown_content)
    assert filepath == "/fake/path/pr_diff.md"

@patch("os.path.join", return_value="/fake/path/pr_diff.md")
@patch("builtins.open", new_callable=mock_open)
def test_save_to_markdown_failure(mock_file, mock_join, extractor):
    """Tests saving markdown to a file with a failure."""
    mock_file.side_effect = Exception("File system error")
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    markdown_content = "## Test Markdown"

    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생:"):
        extractor.save_to_markdown(markdown_content, pr_url)

@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="diff content")
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="/fake/path/pr_diff.md")
def test_extract_diff(mock_save, mock_fetch, extractor):
    """Tests the entire diff extraction process."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    extractor.set_credentials("fake_token", "https://github.sec.samsung.net/api/v3")

    result_path = extractor.extract_diff(pr_url)

    mock_fetch.assert_called_once_with("GAUDI", "gaudi-fe", "8")
    mock_save.assert_called_once()
    assert result_path == "/fake/path/pr_diff.md"

from get_pr_diff_from_github import main

@patch('sys.argv', ['get_pr_diff_from_github.py'])
def test_main_no_args(capsys):
    """Tests the main function with no arguments."""
    with pytest.raises(SystemExit) as e:
        main()

    assert e.type == SystemExit
    assert e.value.code == 1

    captured = capsys.readouterr()
    assert "사용법:" in captured.out

@patch('sys.argv', ['get_pr_diff_from_github.py', 'http://test.com/owner/repo/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value='/path/to/diff.md')
def test_main_success(mock_extract_diff):
    """Tests the main function's success path."""
    main()
    mock_extract_diff.assert_called_once_with('http://test.com/owner/repo/pull/1')

@patch('sys.argv', ['get_pr_diff_from_github.py', 'http://test.com/owner/repo/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=Exception('Test Error'))
def test_main_failure(mock_extract_diff, capsys):
    """Tests the main function's failure path."""
    with pytest.raises(SystemExit) as e:
        main()

    assert e.type == SystemExit
    assert e.value.code == 1

    captured = capsys.readouterr()
    assert "오류 발생: Test Error" in captured.out
