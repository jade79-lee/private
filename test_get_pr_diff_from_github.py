import pytest
import requests
from unittest.mock import patch, mock_open
from datetime import datetime
from get_pr_diff_from_github import GitHubPRDiffExtractor

# Fixture to initialize the extractor
@pytest.fixture
def extractor():
    return GitHubPRDiffExtractor()

# --- Test parse_pr_url ---
def test_parse_pr_url_valid(extractor):
    url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_http(extractor):
    url = "http://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

def test_parse_pr_url_invalid(extractor):
    url = "https://invalid-url.com/some/path"
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url(url)

# --- Test set_credentials ---
def test_set_credentials(extractor):
    token = "test_token"
    api_url = "https://my-ghe-instance.com/api/v3/"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == "https://my-ghe-instance.com/api/v3"
    assert extractor.headers['Authorization'] == f'token {token}'


# --- Test fetch_diff ---
def test_fetch_diff_success(requests_mock, extractor):
    owner, repo, pr_number = "test-owner", "test-repo", "123"
    api_url = "https://api.github.com"
    diff_url = f"{api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    expected_diff = "diff --git a/file.txt b/file.txt"

    extractor.set_credentials("fake_token", api_url)
    requests_mock.get(diff_url, text=expected_diff)

    diff_text = extractor.fetch_diff(owner, repo, pr_number)
    assert diff_text == expected_diff

def test_fetch_diff_no_credentials(extractor):
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")

def test_fetch_diff_api_error(requests_mock, extractor):
    owner, repo, pr_number = "test-owner", "test-repo", "123"
    api_url = "https://api.github.com"
    diff_url = f"{api_url}/repos/{owner}/{repo}/pulls/{pr_number}"

    extractor.set_credentials("fake_token", api_url)
    requests_mock.get(diff_url, status_code=404, reason="Not Found")

    with pytest.raises(RuntimeError, match="Diff API 호출 오류: 404 Client Error: Not Found"):
        extractor.fetch_diff(owner, repo, pr_number)

# --- Test generate_markdown ---
def test_generate_markdown(extractor):
    diff_text = "diff --git a/file.txt b/file.txt"
    pr_url = "https://github.com/user/repo/pull/1"

    markdown = extractor.generate_markdown(diff_text, pr_url)

    assert "# PR Diff" in markdown
    assert f"**PR URL:** {pr_url}" in markdown
    assert "**Repository:** user/repo" in markdown
    assert "**PR Number:** #1" in markdown
    assert "```diff" in markdown
    assert diff_text in markdown

# --- Test save_to_markdown ---
@patch("builtins.open", new_callable=mock_open)
@patch("os.getcwd", return_value="/fake/dir")
def test_save_to_markdown_success(mock_getcwd, mock_file, extractor):
    markdown_content = "# Test Content"
    pr_url = "https://github.com/user/repo/pull/1"

    filepath = extractor.save_to_markdown(markdown_content, pr_url)

    mock_file.assert_called_once()
    handle = mock_file()
    handle.write.assert_called_once_with(markdown_content)
    assert "pr_diff_user_repo_1_" in filepath
    assert filepath.startswith("/fake/dir/")
    assert filepath.endswith(".md")


@patch("builtins.open", mock_open())
@patch("os.getcwd", return_value="/fake/dir")
def test_save_to_markdown_exception(mock_getcwd, extractor):
    # Simulate an error during file write
    m = mock_open()
    m.side_effect = IOError("Disk full")
    with patch("builtins.open", m):
        with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: Disk full"):
            extractor.save_to_markdown("content", "https://github.com/user/repo/pull/1")

# --- Test extract_diff (end-to-end for the class) ---
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="fake_path.md")
@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="fake diff")
def test_extract_diff_success(mock_fetch, mock_save, extractor):
    pr_url = "https://github.com/owner/repo/pull/1"
    extractor.set_credentials("fake_token", "https://api.github.com")

    result_path = extractor.extract_diff(pr_url)

    mock_fetch.assert_called_once_with("owner", "repo", "1")
    mock_save.assert_called_once()
    assert result_path == "fake_path.md"


# --- Test main function ---
@patch('sys.argv', ['script_name.py', 'https://github.com/owner/repo/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value="path/to/file.md")
def test_main_success(mock_extract_diff, capsys):
    from get_pr_diff_from_github import main
    main()
    captured = capsys.readouterr()
    assert "PR Diff 추출이 완료되었습니다." in captured.out
    mock_extract_diff.assert_called_once_with('https://github.com/owner/repo/pull/1')

@patch('sys.argv', ['script_name.py'])
def test_main_no_args(capsys):
    from get_pr_diff_from_github import main
    with pytest.raises(SystemExit) as e:
        main()
    captured = capsys.readouterr()
    assert "사용법:" in captured.out
    assert e.value.code == 1

@patch('sys.argv', ['script_name.py', 'https://github.com/owner/repo/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=ValueError("Test error"))
def test_main_exception(mock_extract_diff, capsys):
    from get_pr_diff_from_github import main
    with pytest.raises(SystemExit) as e:
        main()
    captured = capsys.readouterr()
    assert "오류 발생: Test error" in captured.out
    assert e.value.code == 1

@patch('sys.argv', ['script_name.py', 'https://github.com/owner/repo/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', return_value=None)
def test_main_failure(mock_extract_diff, capsys):
    from get_pr_diff_from_github import main
    main()
    captured = capsys.readouterr()
    assert "PR Diff 추출에 실패했습니다." in captured.out
