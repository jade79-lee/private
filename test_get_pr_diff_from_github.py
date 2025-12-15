import unittest
from get_pr_diff_from_github import GitHubPRDiffExtractor

class TestGitHubPRDiffExtractor(unittest.TestCase):

    def setUp(self):
        # 테스트를 위해 GitHubPRDiffExtractor의 인스턴스를 생성합니다.
        # 환경 변수가 설정되어 있지 않아도 parse_pr_url 메서드는 테스트할 수 있습니다.
        # __init__에서 발생하는 ValueError를 회피하기 위해 임시로 환경변수를 설정합니다.
        import os
        os.environ['GITHUB_TOKEN'] = 'dummy_token'
        os.environ['GITHUB_API_URL'] = 'https://api.github.com'
        self.extractor = GitHubPRDiffExtractor()

    def test_parse_pr_url_valid(self):
        """정상적인 PR URL을 올바르게 파싱하는지 테스트합니다."""
        url = "https://github.com/owner/repo/pull/123"
        owner, repo, pr_number = self.extractor.parse_pr_url(url)
        self.assertEqual(owner, "owner")
        self.assertEqual(repo, "repo")
        self.assertEqual(pr_number, "123")

    def test_parse_pr_url_invalid_no_pull(self):
        """'pull' 키워드가 없는 잘못된 URL에 대해 ValueError를 발생하는지 테스트합니다."""
        url = "https://github.com/owner/repo/issues/123"
        with self.assertRaises(ValueError):
            self.extractor.parse_pr_url(url)

    def test_parse_pr_url_invalid_format(self):
        """형식에 맞지 않는 URL에 대해 ValueError를 발생하는지 테스트합니다."""
        url = "this-is-not-a-url"
        with self.assertRaises(ValueError):
            self.extractor.parse_pr_url(url)

    def test_parse_pr_url_with_enterprise_server(self):
        """GitHub Enterprise 서버 URL도 올바르게 파싱하는지 테스트합니다."""
        url = "https://github.sec.samsung.net/GAUDI/gaudi-fe/pull/8"
        owner, repo, pr_number = self.extractor.parse_pr_url(url)
        self.assertEqual(owner, "GAUDI")
        self.assertEqual(repo, "gaudi-fe")
        self.assertEqual(pr_number, "8")

if __name__ == '__main__':
    unittest.main()
