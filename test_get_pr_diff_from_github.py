import pytest
import requests
import os
from unittest.mock import patch, mock_open
from datetime import datetime

from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """Returns a GitHubPRDiffExtractor instance."""
    return GitHubPRDiffExtractor()

def test_parse_pr_url_valid(extractor):
    """Tests parsing a valid PR URL."""
    url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid(extractor):
    """Tests parsing an invalid PR URL."""
    url = "https://invalid-url.com"
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url(url)

def test_set_credentials(extractor):
    """Tests setting GitHub credentials."""
    token = "test_token"
    api_url = "https://api.github.com"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == api_url
    assert extractor.headers['Authorization'] == f'token {token}'

def test_fetch_diff_success(requests_mock, extractor):
    """Tests fetching a diff successfully."""
    owner = "GAUDI"
    repo = "gaudi-fe"
    pr_number = "8"
    extractor.set_credentials("test_token", "https://api.github.com")
    diff_url = f"{extractor.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, text="diff content")
    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == "diff content"

def test_fetch_diff_failure(requests_mock, extractor):
    """Tests fetching a diff with a request failure."""
    owner = "GAUDI"
    repo = "gaudi-fe"
    pr_number = "8"
    extractor.set_credentials("test_token", "https://api.github.com")
    diff_url = f"{extractor.git_api_base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    requests_mock.get(diff_url, status_code=404)
    with pytest.raises(RuntimeError, match="Diff API 호출 오류"):
        extractor.fetch_diff(owner, repo, pr_number)

def test_fetch_diff_no_credentials(extractor):
    """Tests fetching a diff without setting credentials."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")


def test_generate_markdown(extractor):
    """Tests generating markdown from a diff."""
    diff_text = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py"
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "# PR Diff" in markdown
    assert "PR URL:** https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8" in markdown
    assert "Repository:** GAUDI/gaudi-fe" in markdown
    assert "PR Number:** #8" in markdown
    assert "```diff" in markdown
    assert diff_text in markdown
    assert "```" in markdown

@patch("os.path.join")
@patch("builtins.open", new_callable=mock_open)
def test_save_to_markdown(mock_file, mock_join, extractor):
    """Tests saving markdown to a file."""
    markdown_content = "# PR Diff"
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"pr_diff_GAUDI_gaudi-fe_8_{timestamp}.md"
    mock_join.return_value = f"/test/path/{filename}"
    filepath = extractor.save_to_markdown(markdown_content, pr_url)
    mock_file.assert_called_once_with(f"/test/path/{filename}", 'w', encoding='utf-8')
    mock_file().write.assert_called_once_with(markdown_content)
    assert filepath == f"/test/path/{filename}"

@patch("os.path.join")
@patch("builtins.open", side_effect=IOError("Disk full"))
def test_save_to_markdown_failure(mock_file, mock_join, extractor):
    """Tests saving markdown to a file with a file IO error."""
    markdown_content = "# PR Diff"
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"pr_diff_GAUDI_gaudi-fe_8_{timestamp}.md"
    mock_join.return_value = f"/test/path/{filename}"
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생"):
        extractor.save_to_markdown(markdown_content, pr_url)

@patch.object(GitHubPRDiffExtractor, 'save_to_markdown')
@patch.object(GitHubPRDiffExtractor, 'generate_markdown')
@patch.object(GitHubPRDiffExtractor, 'fetch_diff')
def test_extract_diff(mock_fetch, mock_generate, mock_save, extractor):
    """Tests the entire diff extraction process."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    mock_fetch.return_value = "diff content"
    mock_generate.return_value = "markdown content"
    mock_save.return_value = "/path/to/file.md"
    extractor.set_credentials("test_token", "https://api.github.com")

    result_path = extractor.extract_diff(pr_url)

    mock_fetch.assert_called_once_with("GAUDI", "gaudi-fe", "8")
    mock_generate.assert_called_once_with("diff content", pr_url)
    mock_save.assert_called_once_with("markdown content", pr_url)
    assert result_path == "/path/to/file.md"

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(mock_extractor_class, capsys):
    """Tests the main function with a successful run."""
    instance = mock_extractor_class.return_value
    instance.extract_diff.return_value = "/path/to/file.md"

    with patch('sys.argv', ['get_pr_diff_from_github.py', 'http://some/url']):
        main()

    instance.extract_diff.assert_called_once_with('http://some/url')
    captured = capsys.readouterr()
    assert "PR Diff 추출이 완료되었습니다." in captured.out

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_extraction_fails(mock_extractor_class, capsys):
    """Tests the main function when extraction returns None."""
    instance = mock_extractor_class.return_value
    instance.extract_diff.return_value = None

    with patch('sys.argv', ['get_pr_diff_from_github.py', 'http://some/url']):
        main()

    captured = capsys.readouterr()
    assert "PR Diff 추출에 실패했습니다." in captured.out

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_exception(mock_extractor_class, capsys):
    """Tests the main function when an exception occurs."""
    instance = mock_extractor_class.return_value
    instance.extract_diff.side_effect = Exception("Test Error")

    with patch('sys.argv', ['get_pr_diff_from_github.py', 'http://some/url']):
        with pytest.raises(SystemExit) as e:
            main()

    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "오류 발생: Test Error" in captured.out

def test_main_invalid_args(capsys):
    """Tests the main function with invalid arguments."""
    with patch('sys.argv', ['get_pr_diff_from_github.py']):
        with pytest.raises(SystemExit) as e:
            main()

    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "사용법:" in captured.out
