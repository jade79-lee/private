
import pytest
from unittest.mock import patch
from get_pr_diff_from_github import GitHubPRDiffExtractor, main

def test_parse_pr_url():
    """
    Tests that the PR URL is parsed correctly.
    """
    extractor = GitHubPRDiffExtractor()
    owner, repo, pr_number = extractor.parse_pr_url("https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8")
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid():
    """
    Tests that an invalid PR URL raises a ValueError.
    """
    extractor = GitHubPRDiffExtractor()
    with pytest.raises(ValueError):
        extractor.parse_pr_url("invalid_url")

def test_set_credentials():
    """
    Tests that the credentials are set correctly.
    """
    extractor = GitHubPRDiffExtractor()
    extractor.set_credentials("test_token", "https://api.github.com")
    assert extractor.git_token == "test_token"
    assert extractor.git_api_base_url == "https://api.github.com"
    assert extractor.headers["Authorization"] == "token test_token"

def test_fetch_diff(requests_mock):
    """
    Tests that the diff is fetched correctly.
    """
    extractor = GitHubPRDiffExtractor()
    extractor.set_credentials("test_token", "https://api.github.com")
    requests_mock.get("https://api.github.com/repos/owner/repo/pulls/1", text="diff_text")
    diff = extractor.fetch_diff("owner", "repo", "1")
    assert diff == "diff_text"

def test_fetch_diff_error(requests_mock):
    """
    Tests that an error is raised when the diff cannot be fetched.
    """
    extractor = GitHubPRDiffExtractor()
    extractor.set_credentials("test_token", "https://api.github.com")
    requests_mock.get("https://api.github.com/repos/owner/repo/pulls/1", status_code=404)
    with pytest.raises(RuntimeError):
        extractor.fetch_diff("owner", "repo", "1")

def test_generate_markdown():
    """
    Tests that the markdown is generated correctly.
    """
    extractor = GitHubPRDiffExtractor()
    markdown = extractor.generate_markdown("diff_text", "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8")
    assert "PR URL:** https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8" in markdown
    assert "Repository:** GAUDI/gaudi-fe" in markdown
    assert "PR Number:** #8" in markdown
    assert "```diff\ndiff_text\n```" in markdown

from unittest.mock import patch, mock_open

def test_save_to_markdown():
    """
    Tests that the markdown is saved correctly.
    """
    extractor = GitHubPRDiffExtractor()
    with patch("builtins.open", mock_open()) as mock_file:
        filepath = extractor.save_to_markdown("markdown_content", "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8")
        mock_file.assert_called_once()
        # check if the filename is correct without the timestamp
        assert "pr_diff_GAUDI_gaudi-fe_8" in filepath
        assert filepath.endswith(".md")

def test_main_no_args(capsys):
    """
    Tests that the main function exits when no arguments are provided.
    """
    with patch("sys.argv", ["get_pr_diff_from_github.py"]):
        with pytest.raises(SystemExit):
            main()
    captured = capsys.readouterr()
    assert "사용법" in captured.out

def test_main_too_many_args(capsys):
    """
    Tests that the main function exits when too many arguments are provided.
    """
    with patch("sys.argv", ["get_pr_diff_from_github.py", "url1", "url2"]):
        with pytest.raises(SystemExit):
            main()
    captured = capsys.readouterr()
    assert "사용법" in captured.out

@patch("get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff")
def test_main_success(mock_extract_diff):
    """
    Tests that the main function succeeds.
    """
    mock_extract_diff.return_value = "filepath"
    with patch("sys.argv", ["get_pr_diff_from_github.py", "url"]):
        main()

@patch("get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff")
def test_main_failure(mock_extract_diff):
    """
    Tests that the main function fails.
    """
    mock_extract_diff.side_effect = Exception("error")
    with patch("sys.argv", ["get_pr_diff_from_github.py", "url"]):
        with pytest.raises(SystemExit):
            main()

def test_extract_diff(requests_mock):
    """
    Tests the entire diff extraction process.
    """
    extractor = GitHubPRDiffExtractor()
    extractor.set_credentials("test_token", "https://api.github.com")
    requests_mock.get("https://api.github.com/repos/GAUDI/gaudi-fe/pulls/8", text="diff_text")
    with patch("builtins.open", mock_open()) as mock_file:
        filepath = extractor.extract_diff("https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8")
        mock_file.assert_called_once()
        assert "pr_diff_GAUDI_gaudi-fe_8" in filepath
        assert filepath.endswith(".md")
