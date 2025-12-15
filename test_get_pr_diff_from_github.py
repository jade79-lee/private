
import pytest
from unittest.mock import patch, MagicMock, mock_open
import requests
from get_pr_diff_from_github import GitHubPRDiffExtractor, main
import sys

@pytest.fixture
def extractor():
    """Returns a GitHubPRDiffExtractor instance."""
    return GitHubPRDiffExtractor()

def test_set_credentials(extractor):
    """set_credentials 메서드가 토큰, API URL, 헤더를 올바르게 설정하는지 테스트"""
    token = "test_token"
    api_url = "https://api.github.com"
    extractor.set_credentials(token, api_url)
    assert extractor.git_token == token
    assert extractor.git_api_base_url == api_url
    assert extractor.headers['Authorization'] == f'token {token}'

def test_parse_pr_url_valid(extractor):
    """parse_pr_url 메서드가 유효한 URL을 올바르게 파싱하는지 테스트"""
    url = "https://github.sec.samsung.net/owner/repo/pull/123"
    owner, repo, pr_number = extractor.parse_pr_url(url)
    assert owner == "owner"
    assert repo == "repo"
    assert pr_number == "123"

def test_parse_pr_url_invalid(extractor):
    """parse_pr_url 메서드가 유효하지 않은 URL에 대해 ValueError를 발생하는지 테스트"""
    with pytest.raises(ValueError, match="유효하지 않은 PR URL 형식입니다."):
        extractor.parse_pr_url("invalid_url")

@patch('requests.get')
def test_fetch_diff_success(mock_get, extractor):
    """fetch_diff 메서드가 성공적으로 diff를 가져오는지 테스트"""
    mock_response = MagicMock()
    mock_response.text = "diff content"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    extractor.set_credentials("test_token", "https://api.github.com")
    diff = extractor.fetch_diff("owner", "repo", "123")
    assert diff == "diff content"

@patch('requests.get')
def test_fetch_diff_failure(mock_get, extractor):
    """fetch_diff 메서드가 API 호출 실패 시 RuntimeError를 발생하는지 테스트"""
    mock_get.side_effect = requests.exceptions.RequestException("API Error")
    extractor.set_credentials("test_token", "https://api.github.com")
    with pytest.raises(RuntimeError, match="Diff API 호출 오류: API Error"):
        extractor.fetch_diff("owner", "repo", "123")

def test_fetch_diff_no_credentials(extractor):
    """fetch_diff 메서드가 인증 정보 없이 호출될 때 ValueError를 발생하는지 테스트"""
    with pytest.raises(ValueError, match="Git token과 API Base URL을 먼저 설정해주세요."):
        extractor.fetch_diff("owner", "repo", "123")

def test_generate_markdown(extractor):
    """generate_markdown 메서드가 올바른 형식의 마크다운을 생성하는지 테스트"""
    diff_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/123"
    markdown = extractor.generate_markdown(diff_text, pr_url)
    assert "# PR Diff" in markdown
    assert f"**PR URL:** {pr_url}" in markdown
    assert "```diff" in markdown
    assert diff_text in markdown

@patch('builtins.open', new_callable=mock_open)
@patch('os.path.join', return_value='/fake/path/pr_diff.md')
def test_save_to_markdown_success(mock_join, mock_file, extractor):
    """save_to_markdown 메서드가 성공적으로 파일을 저장하는지 테스트"""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/123"
    filepath = extractor.save_to_markdown("markdown content", pr_url)
    mock_file.assert_called_once_with('/fake/path/pr_diff.md', 'w', encoding='utf-8')
    assert filepath == '/fake/path/pr_diff.md'

@patch('builtins.open', side_effect=IOError("File Error"))
def test_save_to_markdown_failure(mock_open, extractor):
    """save_to_markdown 메서드가 파일 저장 실패 시 RuntimeError를 발생하는지 테스트"""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/123"
    with pytest.raises(RuntimeError, match="파일 저장 중 오류 발생: File Error"):
        extractor.save_to_markdown("markdown content", pr_url)

@patch.object(GitHubPRDiffExtractor, 'parse_pr_url', return_value=("owner", "repo", "123"))
@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value="diff text")
@patch.object(GitHubPRDiffExtractor, 'generate_markdown', return_value="markdown")
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="/path/to/file.md")
def test_extract_diff(mock_save, mock_generate, mock_fetch, mock_parse, extractor):
    """extract_diff 메서드가 전체 프로세스를 올바르게 실행하는지 테스트"""
    pr_url = "https://github.sec.samsung.net/owner/repo/pull/123"
    result_path = extractor.extract_diff(pr_url)

    mock_parse.assert_called_with(pr_url)
    mock_fetch.assert_called_with("owner", "repo", "123")
    mock_generate.assert_called_with("diff text", pr_url)
    mock_save.assert_called_with("markdown", pr_url)
    assert result_path == "/path/to/file.md"

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(MockExtractor):
    """main 함수가 성공적으로 실행되는지 테스트"""
    instance = MockExtractor.return_value
    instance.extract_diff.return_value = "/path/to/diff.md"
    with patch.object(sys, 'argv', ['get_pr_diff_from_github.py', 'http://valid.url']):
        main()
        instance.extract_diff.assert_called_once_with('http://valid.url')

@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_failure(MockExtractor):
    """main 함수가 실패 시 sys.exit(1)을 호출하는지 테스트"""
    instance = MockExtractor.return_value
    instance.extract_diff.side_effect = Exception("Test error")
    with patch.object(sys, 'argv', ['get_pr_diff_from_github.py', 'http://valid.url']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.type == SystemExit
        assert e.value.code == 1

def test_main_invalid_args(capsys):
    """main 함수가 인자 없이 호출될 때 사용법을 출력하고 sys.exit(1)을 호출하는지 테스트"""
    with patch.object(sys, 'argv', ['get_pr_diff_from_github.py']):
        with pytest.raises(SystemExit) as e:
            main()

        captured = capsys.readouterr()
        assert "사용법" in captured.out
        assert e.type == SystemExit
        assert e.value.code == 1
