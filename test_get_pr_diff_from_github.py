
import pytest
import os
import requests
from unittest.mock import patch, MagicMock, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """Returns a GitHubPRDiffExtractor instance."""
    return GitHubPRDiffExtractor()

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
    with pytest.raises(ValueError):
        extractor.parse_pr_url("invalid_url")

@patch('requests.get')
def test_fetch_diff_success(mock_get, extractor):
    """Test fetching a diff successfully."""
    mock_response = MagicMock()
    mock_response.text = "diff content"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    extractor.set_credentials("test_token", "https://api.github.com")
    diff = extractor.fetch_diff("owner", "repo", "123")
    assert diff == "diff content"

def test_fetch_diff_no_credentials(extractor):
    """Test fetching a diff without credentials."""
    with pytest.raises(ValueError):
        extractor.fetch_diff("owner", "repo", "123")

@patch('requests.get')
def test_fetch_diff_api_error(mock_get, extractor):
    """Test fetching a diff with an API error."""
    mock_get.side_effect = requests.exceptions.RequestException("API Error")
    extractor.set_credentials("test_token", "https://api.github.com")
    with pytest.raises(RuntimeError):
        extractor.fetch_diff("owner", "repo", "123")

def test_generate_markdown(extractor):
    """Test generating markdown."""
    diff_text = "diff content"
    pr_url = "https://github.com/owner/repo/pull/123"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "# PR Diff" in markdown
    assert "owner/repo" in markdown
    assert "#123" in markdown
    assert "```diff\ndiff content\n```" in markdown

@patch('os.path.join')
@patch('builtins.open', new_callable=mock_open)
def test_save_to_markdown_success(mock_file, mock_join, extractor):
    """Test saving markdown to a file successfully."""
    mock_join.return_value = "test_file.md"
    markdown_content = "markdown content"
    pr_url = "https://github.com/owner/repo/pull/123"
    filepath = extractor.save_to_markdown(markdown_content, pr_url)
    assert filepath == "test_file.md"
    mock_file.assert_called_once_with("test_file.md", 'w', encoding='utf-8')
    mock_file().write.assert_called_once_with(markdown_content)

@patch('os.path.join')
@patch('builtins.open', new_callable=mock_open)
def test_save_to_markdown_error(mock_file, mock_join, extractor):
    """Test saving markdown to a file with an error."""
    mock_file.side_effect = Exception("File Error")
    mock_join.return_value = "test_file.md"
    markdown_content = "markdown content"
    pr_url = "https://github.com/owner/repo/pull/123"
    with pytest.raises(RuntimeError):
        extractor.save_to_markdown(markdown_content, pr_url)

@patch.object(GitHubPRDiffExtractor, 'parse_pr_url', return_value=("owner", "repo", "123"))
@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="diff content")
@patch.object(GitHubPRDiffExtractor, 'generate_markdown', return_value="markdown content")
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="test_file.md")
def test_extract_diff(mock_save, mock_generate, mock_fetch, mock_parse, extractor):
    """Test the end-to-end diff extraction process."""
    pr_url = "https://github.com/owner/repo/pull/123"
    result_path = extractor.extract_diff(pr_url)
    assert result_path == "test_file.md"
    mock_parse.assert_called_with(pr_url)
    mock_fetch.assert_called_with("owner", "repo", "123")
    mock_generate.assert_called_with("diff content", pr_url)
    mock_save.assert_called_with("markdown content", pr_url)

@patch('sys.argv', ['get_pr_diff_from_github.py', 'http://a.b/c/d/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(mock_extractor_class):
    """Test the main function with a valid PR URL."""
    mock_extractor_instance = mock_extractor_class.return_value
    mock_extractor_instance.extract_diff.return_value = "path/to/file.md"

    main()

    mock_extractor_class.assert_called_once()
    mock_extractor_instance.extract_diff.assert_called_once_with('http://a.b/c/d/pull/1')

@patch('sys.argv', ['get_pr_diff_from_github.py'])
@patch('builtins.print')
def test_main_no_args(mock_print):
    """Test the main function with no arguments."""
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    mock_print.assert_any_call("사용법: python get_pr_diff_from_github.py <PR_URL>")

@patch('sys.argv', ['get_pr_diff_from_github.py', 'http://a.b/c/d/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
@patch('builtins.print')
def test_main_extractor_fail(mock_print, mock_extractor_class):
    """Test the main function when the extractor fails."""
    mock_extractor_instance = mock_extractor_class.return_value
    mock_extractor_instance.extract_diff.return_value = None

    main()

    mock_print.assert_any_call("PR Diff 추출에 실패했습니다.")

@patch('sys.argv', ['get_pr_diff_from_github.py', 'http://a.b/c/d/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
@patch('builtins.print')
def test_main_exception(mock_print, mock_extractor_class):
    """Test the main function when an exception occurs."""
    mock_extractor_instance = mock_extractor_class.return_value
    mock_extractor_instance.extract_diff.side_effect = Exception("Test error")

    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    mock_print.assert_any_call("오류 발생: Test error")
