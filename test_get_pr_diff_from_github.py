import pytest
import requests
from unittest.mock import patch, MagicMock
from get_pr_diff_from_github import GitHubPRDiffExtractor, main

# 테스트용 상수
FAKE_TOKEN = "fake_token"
FAKE_API_URL = "https://fake.api.com"
FAKE_PR_URL = "https://fake.api.com/owner/repo/pull/1"
FAKE_OWNER = "owner"
FAKE_REPO = "repo"
FAKE_PR_NUMBER = "1"
FAKE_DIFF_TEXT = "diff --git a/file.py b/file.py"


@pytest.fixture
def extractor():
    """GitHubPRDiffExtractor 인스턴스를 생성하고 초기화합니다."""
    instance = GitHubPRDiffExtractor()
    instance.set_credentials(FAKE_TOKEN, FAKE_API_URL)
    return instance


def test_set_credentials(extractor):
    """set_credentials가 토큰과 API URL을 올바르게 설정하는지 테스트합니다."""
    assert extractor.git_token == FAKE_TOKEN
    assert extractor.git_api_base_url == FAKE_API_URL
    assert extractor.headers['Authorization'] == f'token {FAKE_TOKEN}'


def test_parse_pr_url(extractor):
    """parse_pr_url이 URL을 올바르게 파싱하는지 테스트합니다."""
    owner, repo, pr_number = extractor.parse_pr_url(FAKE_PR_URL)
    assert owner == FAKE_OWNER
    assert repo == FAKE_REPO
    assert pr_number == FAKE_PR_NUMBER


def test_parse_pr_url_invalid(extractor):
    """parse_pr_url이 유효하지 않은 URL에 대해 ValueError를 발생하는지 테스트합니다."""
    with pytest.raises(ValueError):
        extractor.parse_pr_url("invalid_url")


@patch('requests.get')
def test_fetch_diff_success(mock_get, extractor):
    """fetch_diff가 API 호출에 성공하고 diff 텍스트를 반환하는지 테스트합니다."""
    mock_response = MagicMock()
    mock_response.text = FAKE_DIFF_TEXT
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    diff = extractor.fetch_diff(FAKE_OWNER, FAKE_REPO, FAKE_PR_NUMBER)
    assert diff == FAKE_DIFF_TEXT


@patch('requests.get')
def test_fetch_diff_failure(mock_get, extractor):
    """fetch_diff가 API 호출 실패 시 RuntimeError를 발생하는지 테스트합니다."""
    mock_get.side_effect = requests.exceptions.RequestException("API Error")
    with pytest.raises(RuntimeError):
        extractor.fetch_diff(FAKE_OWNER, FAKE_REPO, FAKE_PR_NUMBER)


def test_fetch_diff_no_credentials():
    """자격 증명이 설정되지 않았을 때 fetch_diff가 ValueError를 발생하는지 테스트합니다."""
    extractor = GitHubPRDiffExtractor()
    with pytest.raises(ValueError):
        extractor.fetch_diff(FAKE_OWNER, FAKE_REPO, FAKE_PR_NUMBER)


def test_generate_markdown(extractor):
    """generate_markdown이 올바른 형식의 마크다운을 생성하는지 테스트합니다."""
    markdown = extractor.generate_markdown(FAKE_DIFF_TEXT, FAKE_PR_URL)
    assert f"**PR URL:** {FAKE_PR_URL}" in markdown
    assert f"```diff\n{FAKE_DIFF_TEXT}\n```" in markdown


@patch('builtins.open')
@patch('os.getcwd', return_value="/fake/dir")
def test_save_to_markdown_success(mock_getcwd, mock_open, extractor):
    """save_to_markdown이 성공적으로 파일을 저장하는지 테스트합니다."""
    filepath = extractor.save_to_markdown("markdown_content", FAKE_PR_URL)
    mock_open.assert_called_once()
    assert "pr_diff_owner_repo_1" in filepath


@patch('builtins.open', side_effect=IOError("File Error"))
@patch('os.getcwd', return_value="/fake/dir")
def test_save_to_markdown_failure(mock_getcwd, mock_open, extractor):
    """save_to_markdown이 파일 저장 실패 시 RuntimeError를 발생하는지 테스트합니다."""
    with pytest.raises(RuntimeError):
        extractor.save_to_markdown("markdown_content", FAKE_PR_URL)


@patch.object(GitHubPRDiffExtractor, 'fetch_diff', return_value=FAKE_DIFF_TEXT)
@patch.object(GitHubPRDiffExtractor, 'save_to_markdown', return_value="/fake/path")
def test_extract_diff(mock_save, mock_fetch, extractor):
    """extract_diff의 전체 흐름을 테스트합니다."""
    result_path = extractor.extract_diff(FAKE_PR_URL)
    mock_fetch.assert_called_once()
    mock_save.assert_called_once()
    assert result_path == "/fake/path"


@patch('sys.argv', ['script.py', FAKE_PR_URL])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_success(MockExtractor, capsys):
    """main 함수가 성공적으로 실행되는지 테스트합니다."""
    mock_instance = MockExtractor.return_value
    mock_instance.extract_diff.return_value = "/fake/path"
    main()
    captured = capsys.readouterr()
    assert "PR Diff 추출이 완료되었습니다." in captured.out


@patch('sys.argv', ['script.py'])
def test_main_invalid_args(capsys):
    """main 함수가 잘못된 인자로 호출될 때 에러를 출력하고 종료하는지 테스트합니다."""
    with pytest.raises(SystemExit) as e:
        main()
    captured = capsys.readouterr()
    assert "사용법" in captured.out
    assert e.value.code == 1


@patch('sys.argv', ['script.py', FAKE_PR_URL])
@patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
def test_main_exception(MockExtractor, capsys):
    """main 함수에서 예외 발생 시 에러를 출력하고 종료하는지 테스트합니다."""
    MockExtractor.return_value.extract_diff.side_effect = Exception("Test Error")
    with pytest.raises(SystemExit) as e:
        main()
    captured = capsys.readouterr()
    assert "오류 발생: Test Error" in captured.out
    assert e.value.code == 1
