
import pytest
import requests_mock
from unittest.mock import patch
from datetime import datetime
from get_pr_diff_from_github import GitHubPRDiffExtractor, main

@pytest.fixture
def extractor():
    """GitHubPRDiffExtractor 인스턴스를 생성하는 Fixture"""
    return GitHubPRDiffExtractor()

def test_parse_pr_url_valid(extractor):
    """유효한 PR URL 파싱 테스트"""
    owner, repo, pr_number = extractor.parse_pr_url("https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8")
    assert owner == "GAUDI"
    assert repo == "gaudi-fe"
    assert pr_number == "8"

    owner, repo, pr_number = extractor.parse_pr_url("http://github.sec.samsung.net/owner/repo/pull/123")
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid(extractor):
    """유효하지 않은 PR URL 파싱 테스트"""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("https://invalid-url.com")

    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/")

    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("https://github.sec.samsung.net/GAUDI/gaudi-fe/pulls/8") # 'pulls'는 잘못된 경로

    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("just a string")

def test_set_credentials(extractor):
    """자격 증명 설정 테스트"""
    token = "test_token"
    api_url = "https://my-api.com/api/v3/"
    extractor.set_credentials(token, api_url)

    assert extractor.git_token == token
    assert extractor.git_api_base_url == "https://my-api.com/api/v3" # Trailing slash should be removed
    assert extractor.headers['Authorization'] == f'token {token}'

def test_fetch_diff_success(extractor, requests_mock):
    """Diff 가져오기 성공 테스트"""
    extractor.set_credentials("test_token", "https://api.github.com")
    diff_url = "https://api.github.com/repos/owner/repo/pulls/1"
    requests_mock.get(diff_url, text="diff --git a/file.txt b/file.txt")

    diff = extractor.fetch_diff("owner", "repo", "1")
    assert diff == "diff --git a/file.txt b/file.txt"

def test_fetch_diff_failure(extractor, requests_mock):
    """Diff 가져오기 실패 테스트"""
    extractor.set_credentials("test_token", "https://api.github.com")
    diff_url = "https://api.github.com/repos/owner/repo/pulls/1"
    requests_mock.get(diff_url, status_code=404, reason="Not Found")

    with pytest.raises(RuntimeError, match="Diff API 호출 오류: 404 Client Error: Not Found"):
        extractor.fetch_diff("owner", "repo", "1")

def test_fetch_diff_no_credentials(extractor):
    """자격 증명 없이 Diff 가져오기 테스트"""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "1")

@patch('get_pr_diff_from_github.datetime')
def test_generate_markdown(mock_datetime, extractor):
    """Markdown 생성 테스트"""
    mock_now = datetime(2023, 10, 27, 10, 0, 0)
    mock_datetime.now.return_value = mock_now

    diff_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    pr_url = "https://github.com/owner/repo/pull/123"

    markdown = extractor.generate_markdown(diff_text, pr_url)

    expected_header = (
        "# PR Diff\n\n"
        "**PR URL:** https://github.com/owner/repo/pull/123\n"
        "**Repository:** owner/repo\n"
        "**PR Number:** #123\n"
        "**추출 시간:** 2023-10-27 10:00:00\n\n"
        "---\n\n"
    )
    expected_body = f"```diff\n{diff_text}\n```\n"
    expected_markdown = expected_header + expected_body

    assert markdown == expected_markdown

@patch('get_pr_diff_from_github.os.getcwd')
@patch('get_pr_diff_from_github.datetime')
def test_save_to_markdown(mock_datetime, mock_getcwd, extractor, tmp_path):
    """Markdown 파일 저장 테스트"""
    mock_now = datetime(2023, 10, 27, 10, 30, 0)
    mock_datetime.now.return_value = mock_now
    mock_getcwd.return_value = str(tmp_path)

    markdown_content = "# Test Content"
    pr_url = "https://github.com/owner/repo/pull/1"

    filepath = extractor.save_to_markdown(markdown_content, pr_url)

    expected_filename = "pr_diff_owner_repo_1_20231027_103000.md"
    expected_filepath = tmp_path / expected_filename

    assert filepath == str(expected_filepath)
    assert expected_filepath.exists()
    assert expected_filepath.read_text(encoding='utf-8') == markdown_content

@patch('get_pr_diff_from_github.os.getcwd')
def test_save_to_markdown_error(mock_getcwd, extractor, tmp_path):
    """Markdown 파일 저장 오류 테스트"""
    # Make the temporary directory read-only to trigger a write error
    mock_getcwd.return_value = str(tmp_path)
    tmp_path.chmod(0o555)

    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생"):
         extractor.save_to_markdown("content", "https://github.com/owner/repo/pull/1")

    # Restore permissions for cleanup
    tmp_path.chmod(0o755)

@patch('get_pr_diff_from_github.sys.argv', ['script.py', 'https://github.com/owner/repo/pull/1'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(MockExtractor, capsys):
    """메인 함수 성공 테스트"""
    mock_instance = MockExtractor.return_value
    mock_instance.extract_diff.return_value = "/path/to/diff.md"

    main()

    mock_instance.extract_diff.assert_called_once_with('https://github.com/owner/repo/pull/1')
    captured = capsys.readouterr()
    assert "PR Diff 추출이 완료되었습니다." in captured.out

@patch('get_pr_diff_from_github.sys.argv', ['script.py'])
def test_main_no_args(capsys):
    """메인 함수 인자 없는 경우 테스트"""
    with pytest.raises(SystemExit) as e:
        main()

    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "사용법: python" in captured.out

@patch('get_pr_diff_from_github.sys.argv', ['script.py', 'url'])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_extractor_exception(MockExtractor, capsys):
    """메인 함수 예외 처리 테스트"""
    mock_instance = MockExtractor.return_value
    mock_instance.extract_diff.side_effect = Exception("Test error")

    with pytest.raises(SystemExit) as e:
        main()

    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "오류 발생: Test error" in captured.out
