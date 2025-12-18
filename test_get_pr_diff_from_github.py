
import pytest
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import os
import re
import requests
import sys
import io

@pytest.fixture
def extractor():
    """Returns an instance of GitHubPRDiffExtractor."""
    return GitHubPRDiffExtractor()

@pytest.fixture
def pr_url():
    """Returns a sample PR URL."""
    return "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"

def test_parse_pr_url(extractor, pr_url):
    """Tests the parsing of a valid PR URL."""
    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid(extractor):
    """Tests the parsing of an invalid PR URL."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid_url")

def test_set_credentials(extractor):
    """Tests setting the GitHub token and API base URL."""
    token = "test_token"
    api_url = "https://api.github.com"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == api_url
    assert extractor.headers['Authorization'] == f"token {token}"

@patch('requests.get')
def test_fetch_diff_success(mock_get, extractor, pr_url):
    """Tests fetching a diff successfully."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "diff --git a/file.py b/file.py"
    extractor.set_credentials("test_token", "https://api.github.com")
    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    diff = extractor.fetch_diff(owner, repo, pr_number)
    assert diff == "diff --git a/file.py b/file.py"

@patch('requests.get')
def test_fetch_diff_failure(mock_get, extractor, pr_url):
    """Tests fetching a diff with a request failure."""
    mock_get.side_effect = requests.exceptions.RequestException("API Error")
    extractor.set_credentials("test_token", "https://api.github.com")
    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    with pytest.raises(RuntimeError, match="Diff API 호출 오류: API Error"):
        extractor.fetch_diff(owner, repo, pr_number)

def test_fetch_diff_no_credentials(extractor, pr_url):
    """Tests fetching a diff without setting credentials."""
    owner, repo, pr_number = extractor.parse_pr_url(pr_url)
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff(owner, repo, pr_number)

def test_generate_markdown(extractor, pr_url):
    """Tests generating markdown from a diff."""
    diff_text = "diff --git a/file.py b/file.py"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert f"**PR URL:** {pr_url}" in markdown
    assert "**Repository:** GAUDI/gaudi-fe" in markdown
    assert "**PR Number:** #8" in markdown
    assert f"```diff\n{diff_text}\n```" in markdown

def test_save_to_markdown(extractor, pr_url, tmp_path):
    """Tests saving markdown to a file."""
    markdown_content = "## PR Diff"

    # Change the current working directory to the temporary directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        filepath = extractor.save_to_markdown(markdown_content, pr_url)
        assert os.path.exists(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            assert f.read() == markdown_content
    finally:
        # Restore the original working directory
        os.chdir(original_cwd)


@patch('builtins.open', new_callable=mock_open)
def test_save_to_markdown_error(mock_file, extractor, pr_url):
    """Tests handling an error when saving a markdown file."""
    mock_file.side_effect = IOError("File system error")
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: File system error"):
        extractor.save_to_markdown("content", pr_url)

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.fetch_diff')
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.save_to_markdown')
def test_extract_diff(mock_save, mock_fetch, extractor, pr_url):
    """Tests the main diff extraction process."""
    mock_fetch.return_value = "diff text"
    mock_save.return_value = "path/to/file.md"
    extractor.set_credentials("test_token", "https://api.github.com")
    result_path = extractor.extract_diff(pr_url)
    mock_fetch.assert_called_once_with("GAUDI", "gaudi-fe", "8")
    mock_save.assert_called_once()
    assert result_path == "path/to/file.md"

@patch('sys.stdout', new_callable=io.StringIO)
def test_main_no_args(mock_stdout):
    """Tests the main function with no arguments."""
    with patch.object(sys, 'argv', ['get_pr_diff_from_github.py']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1
    assert "사용법" in mock_stdout.getvalue()

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff')
@patch('builtins.print')
def test_main_success(mock_print, mock_extract_diff, pr_url):
    """Tests the main function with a successful execution."""
    mock_extract_diff.return_value = "path/to/file.md"
    with patch.object(sys, 'argv', ['get_pr_diff_from_github.py', pr_url]):
        main()
    mock_extract_diff.assert_called_once_with(pr_url)
    mock_print.assert_any_call("PR Diff 추출이 완료되었습니다.")


@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff')
@patch('builtins.print')
def test_main_extract_diff_fails(mock_print, mock_extract_diff, pr_url):
    """Tests the main function when extract_diff returns no path."""
    mock_extract_diff.return_value = None
    with patch.object(sys, 'argv', ['get_pr_diff_from_github.py', pr_url]):
        main()
    mock_extract_diff.assert_called_once_with(pr_url)
    mock_print.assert_any_call("PR Diff 추출에 실패했습니다.")


@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff')
@patch('builtins.print')
def test_main_exception(mock_print, mock_extract_diff, pr_url):
    """Tests the main function when an exception occurs."""
    error_message = "Something went wrong"
    mock_extract_diff.side_effect = Exception(error_message)
    with patch.object(sys, 'argv', ['get_pr_diff_from_github.py', pr_url]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1

    mock_extract_diff.assert_called_once_with(pr_url)
    mock_print.assert_any_call(f"오류 발생: {error_message}")
