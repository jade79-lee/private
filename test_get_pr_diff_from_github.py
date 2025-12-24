
import unittest
from unittest.mock import patch, mock_open
import sys
import os
import requests
import requests_mock
from datetime import datetime

# Add the directory containing the script to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from get_pr_diff_from_github import GitHubPRDiffExtractor, main

class TestGitHubPRDiffExtractor(unittest.TestCase):

    def setUp(self):
        """Set up for the tests."""
        self.extractor = GitHubPRDiffExtractor()
        self.pr_url = "https://github.sec.samsung.net/owner/repo/pull/123"
        self.owner = "owner"
        self.repo = "repo"
        self.pr_number = "123"
        self.token = "test_token"
        self.api_base_url = "https://github.sec.samsung.net/api/v3"

    def test_set_credentials(self):
        """Test setting credentials."""
        self.extractor.set_credentials(self.token, self.api_base_url)
        self.assertEqual(self.extractor.git_token, self.token)
        self.assertEqual(self.extractor.git_api_base_url, self.api_base_url)
        expected_headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3.diff'
        }
        self.assertEqual(self.extractor.headers, expected_headers)

    def test_parse_pr_url_valid(self):
        """Test parsing a valid PR URL."""
        owner, repo, pr_number = self.extractor.parse_pr_url(self.pr_url)
        self.assertEqual(owner, self.owner)
        self.assertEqual(repo, self.repo)
        self.assertEqual(pr_number, self.pr_number)

    def test_parse_pr_url_invalid(self):
        """Test parsing an invalid PR URL."""
        with self.assertRaises(ValueError):
            self.extractor.parse_pr_url("invalid_url")

    def test_fetch_diff_no_credentials(self):
        """Test fetching diff without credentials."""
        with self.assertRaises(ValueError):
            self.extractor.fetch_diff(self.owner, self.repo, self.pr_number)

    @requests_mock.Mocker()
    def test_fetch_diff_success(self, m):
        """Test fetching diff successfully."""
        self.extractor.set_credentials(self.token, self.api_base_url)
        diff_url = f"{self.api_base_url}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
        expected_diff = "diff --git a/file.txt b/file.txt"
        m.get(diff_url, text=expected_diff)

        diff_text = self.extractor.fetch_diff(self.owner, self.repo, self.pr_number)
        self.assertEqual(diff_text, expected_diff)

    @requests_mock.Mocker()
    def test_fetch_diff_failure(self, m):
        """Test fetching diff with an API error."""
        self.extractor.set_credentials(self.token, self.api_base_url)
        diff_url = f"{self.api_base_url}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
        m.get(diff_url, status_code=404)

        with self.assertRaises(RuntimeError):
            self.extractor.fetch_diff(self.owner, self.repo, self.pr_number)

    def test_generate_markdown(self):
        """Test generating markdown from diff text."""
        diff_text = "diff --git a/file.txt b/file.txt"
        markdown = self.extractor.generate_markdown(diff_text, self.pr_url)

        self.assertIn("# PR Diff", markdown)
        self.assertIn(f"**PR URL:** {self.pr_url}", markdown)
        self.assertIn(f"**Repository:** {self.owner}/{self.repo}", markdown)
        self.assertIn(f"**PR Number:** #{self.pr_number}", markdown)
        self.assertIn(f"```diff\n{diff_text}\n```", markdown)

    def test_save_to_markdown_success(self):
        """Test saving markdown to a file."""
        markdown_content = "## Test Markdown"

        with patch("builtins.open", mock_open()) as mocked_file:
            filepath = self.extractor.save_to_markdown(markdown_content, self.pr_url)

            # Check if file was written to
            mocked_file.assert_called_once()
            handle = mocked_file()
            handle.write.assert_called_once_with(markdown_content)

            # Check filename format
            timestamp_regex = datetime.now().strftime('%Y%m%d_')
            self.assertIn(f"pr_diff_{self.owner}_{self.repo}_{self.pr_number}_{timestamp_regex}", filepath)
            self.assertTrue(filepath.endswith(".md"))

    def test_save_to_markdown_failure(self):
        """Test handling an error when saving a file."""
        markdown_content = "## Test Markdown"
        with patch("builtins.open", mock_open()) as mocked_file:
            mocked_file.side_effect = IOError("File system is full")
            with self.assertRaises(RuntimeError):
                self.extractor.save_to_markdown(markdown_content, self.pr_url)

    @patch.object(GitHubPRDiffExtractor, 'save_to_markdown')
    @patch.object(GitHubPRDiffExtractor, 'generate_markdown')
    @patch.object(GitHubPRDiffExtractor, 'fetch_diff')
    @patch.object(GitHubPRDiffExtractor, 'parse_pr_url')
    def test_extract_diff_flow(self, mock_parse, mock_fetch, mock_generate, mock_save):
        """Test the overall diff extraction process flow."""
        mock_parse.return_value = (self.owner, self.repo, self.pr_number)
        mock_fetch.return_value = "fake_diff_text"
        mock_generate.return_value = "fake_markdown"
        mock_save.return_value = "fake_filepath.md"

        result_path = self.extractor.extract_diff(self.pr_url)

        mock_parse.assert_called_with(self.pr_url)
        mock_fetch.assert_called_with(self.owner, self.repo, self.pr_number)
        mock_generate.assert_called_with("fake_diff_text", self.pr_url)
        mock_save.assert_called_with("fake_markdown", self.pr_url)
        self.assertEqual(result_path, "fake_filepath.md")


class TestMainFunction(unittest.TestCase):

    @patch('sys.argv', ['get_pr_diff_from_github.py', 'http://fake.url/owner/repo/pull/1'])
    @patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff')
    def test_main_success(self, mock_extract_diff):
        """Test the main function with correct arguments."""
        mock_extract_diff.return_value = "/path/to/diff.md"

        with patch('builtins.print') as mock_print:
            main()
            # Check for the final success message
            self.assertTrue(any("PR Diff 추출이 완료되었습니다." in call.args[0] for call in mock_print.call_args_list))

    @patch('sys.argv', ['get_pr_diff_from_github.py'])
    def test_main_no_args(self):
        """Test the main function with no PR URL argument."""
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)

    @patch('sys.argv', ['get_pr_diff_from_github.py', 'http://fake.url/owner/repo/pull/1'])
    @patch('get_pr_diff_from_github.GitHubPRDiffExtractor.extract_diff', side_effect=Exception("Test error"))
    def test_main_exception(self, mock_extract_diff):
        """Test the main function when an exception occurs."""
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
