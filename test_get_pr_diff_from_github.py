
import pytest
import requests_mock
import os
import sys
from unittest.mock import patch, mock_open
from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """Provides a GitHubPRDiffExtractor instance for tests."""
    return GitHubPRDiffExtractor()

def test_set_credentials(extractor):
    """Tests setting credentials on the extractor."""
    extractor.set_credentials("test_token", "https://api.github.com")
    assert extractor.git_token == "test_token"
    assert extractor.git_api_base_url == "https://api.github.com"
    assert extractor.headers["Authorization"] == "token test_token"

def test_parse_pr_url(extractor):
    """Tests parsing a valid PR URL."""
    owner, repo, pr_number = extractor.parse_pr_url("https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8")
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid(extractor):
    """Tests parsing an invalid PR URL."""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid_url")

def test_fetch_diff_no_credentials(extractor):
    """Tests that fetching a diff without credentials raises an error."""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "123")

def test_fetch_diff_success(extractor):
    """Tests successfully fetching a diff."""
    extractor.set_credentials("test_token", "https://api.github.com")
    with requests_mock.Mocker() as m:
        m.get("https://api.github.com/repos/owner/repo/pulls/123", text="diff content")
        diff = extractor.fetch_diff("owner", "repo", "123")
        assert diff == "diff content"

def test_fetch_diff_failure(extractor):
    """Tests a failed diff fetch due to an API error."""
    extractor.set_credentials("test_token", "https://api.github.com")
    with requests_mock.Mocker() as m:
        m.get("https://api.github.com/repos/owner/repo/pulls/123", status_code=404)
        with pytest.raises(RuntimeError, match="Diff API 호출 오류"):
            extractor.fetch_diff("owner", "repo", "123")

def test_generate_markdown(extractor):
    """Tests the markdown generation."""
    diff_text = "test diff"
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "**PR URL:** https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8" in markdown
    assert "```diff\ntest diff\n```" in markdown

@patch("get_pr_diff_from_github.datetime")
@patch("builtins.open", new_callable=mock_open)
def test_save_to_markdown(mock_open, mock_datetime, extractor):
    """Tests saving the markdown content to a file."""
    mock_datetime.now.return_value.strftime.return_value = "20230101_120000"
    markdown_content = "test markdown"
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    expected_filename = "pr_diff_GAUDI_gaudi-fe_8_20230101_120000.md"
    expected_filepath = os.path.join(os.getcwd(), expected_filename)

    filepath = extractor.save_to_markdown(markdown_content, pr_url)

    mock_open.assert_called_once_with(expected_filepath, 'w', encoding='utf-8')
    mock_open().write.assert_called_once_with(markdown_content)
    assert filepath == expected_filepath

@patch("builtins.open")
def test_save_to_markdown_failure(mock_open, extractor):
    """Tests a failure during file saving."""
    mock_open.side_effect = IOError("File error")
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: File error"):
        extractor.save_to_markdown("test", "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8")

@patch.object(GitHubPRDiffExtractor, 'save_to_markdown')
@patch.object(GitHubPRDiffExtractor, 'generate_markdown')
@patch.object(GitHubPRDiffExtractor, 'fetch_diff')
def test_extract_diff(mock_fetch, mock_generate, mock_save, extractor):
    """Tests the end-to-end diff extraction process."""
    pr_url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    extractor.set_credentials("test_token", "https://api.github.com")
    mock_fetch.return_value = "diff text"
    mock_generate.return_value = "markdown"
    mock_save.return_value = "filepath"

    result = extractor.extract_diff(pr_url)

    mock_fetch.assert_called_once_with("GAUDI", "gaudi-fe", "8")
    mock_generate.assert_called_once_with("diff text", pr_url)
    mock_save.assert_called_once_with("markdown", pr_url)
    assert result == "filepath"

@patch('sys.argv', ['get_pr_diff_from_github.py', 'https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(mock_extractor_class, capsys):
    """Tests the main function's success path."""
    mock_instance = mock_extractor_class.return_value
    mock_instance.extract_diff.return_value = "some_path"
    main()
    mock_extractor_class.assert_called_once()
    mock_instance.extract_diff.assert_called_once_with('https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8')
    captured = capsys.readouterr()
    assert "PR Diff 추출이 완료되었습니다." in captured.out

@patch('sys.argv', ['get_pr_diff_from_github.py', 'https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_failure_no_result(mock_extractor_class, capsys):
    """Tests the main function's failure path when no result is returned."""
    mock_instance = mock_extractor_class.return_value
    mock_instance.extract_diff.return_value = None
    main()
    captured = capsys.readouterr()
    assert "PR Diff 추출에 실패했습니다." in captured.out

@patch('sys.argv', ['get_pr_diff_from_github.py'])
def test_main_no_args(capsys):
    """Tests the main function with no command-line arguments."""
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "사용법:" in captured.out

@patch('sys.argv', ['get_pr_diff_from_github.py', 'some_url'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_exception(mock_extractor_class, capsys):
    """Tests the main function when an exception occurs."""
    mock_instance = mock_extractor_class.return_value
    mock_instance.extract_diff.side_effect = Exception("Test error")
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "오류 발생: Test error" in captured.out
