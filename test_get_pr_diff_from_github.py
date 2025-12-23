
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import requests
from datetime import datetime

# Add the script's directory to the Python path to allow importing
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from get_pr_diff_from_github import GitHubPRDiffExtractor, main

class TestGitHubPRDiffExtractor(unittest.TestCase):

    def setUp(self):
        """Set up a test instance of the extractor."""
        self.extractor = GitHubPRDiffExtractor()
        self.pr_url = "https://github.sec.samsung.net/owner/repo/pull/123"
        self.owner = "owner"
        self.repo = "repo"
        self.pr_number = "123"
        self.git_token = "test_token"
        self.api_base_url = "https://github.sec.samsung.net/api/v3"

    def test_set_credentials(self):
        """Test that credentials are set correctly."""
        self.extractor.set_credentials(self.git_token, self.api_base_url)
        self.assertEqual(self.extractor.git_token, self.git_token)
        self.assertEqual(self.extractor.git_api_base_url, self.api_base_url)
        self.assertIn(f'token {self.git_token}', self.extractor.headers['Authorization'])

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

    @patch('requests.get')
    def test_fetch_diff_success(self, mock_get):
        """Test successfully fetching a diff."""
        mock_response = MagicMock()
        mock_response.text = "diff --git a/file.py b/file.py"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        self.extractor.set_credentials(self.git_token, self.api_base_url)
        diff = self.extractor.fetch_diff(self.owner, self.repo, self.pr_number)

        self.assertEqual(diff, "diff --git a/file.py b/file.py")
        diff_url = f"{self.api_base_url}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
        mock_get.assert_called_once_with(diff_url, headers=self.extractor.headers)

    def test_fetch_diff_no_credentials(self):
        """Test fetching diff without credentials."""
        with self.assertRaises(ValueError):
            self.extractor.fetch_diff(self.owner, self.repo, self.pr_number)

    @patch('requests.get')
    def test_fetch_diff_api_error(self, mock_get):
        """Test API error during diff fetching."""
        mock_get.side_effect = requests.exceptions.RequestException("API Error")
        self.extractor.set_credentials(self.git_token, self.api_base_url)
        with self.assertRaises(RuntimeError):
            self.extractor.fetch_diff(self.owner, self.repo, self.pr_number)

    def test_generate_markdown(self):
        """Test generating markdown from diff text."""
        diff_text = "diff --git a/file.py b/file.py"
        markdown = self.extractor.generate_markdown(diff_text, self.pr_url)
        self.assertIn("# PR Diff", markdown)
        self.assertIn(f"**PR URL:** {self.pr_url}", markdown)
        self.assertIn(f"```diff\n{diff_text}\n```", markdown)

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.join')
    def test_save_to_markdown_success(self, mock_path_join, mock_file):
        """Test successfully saving markdown to a file."""
        mock_path_join.return_value = "/fake/path/pr_diff.md"
        filepath = self.extractor.save_to_markdown("markdown content", self.pr_url)
        mock_file.assert_called_once_with("/fake/path/pr_diff.md", 'w', encoding='utf-8')
        mock_file().write.assert_called_once_with("markdown content")
        self.assertEqual(filepath, "/fake/path/pr_diff.md")

    @patch('builtins.open', new_callable=mock_open)
    def test_save_to_markdown_error(self, mock_open_instance):
        """Test error while saving markdown file."""
        mock_open_instance.side_effect = Exception("File Error")
        with self.assertRaises(RuntimeError):
            self.extractor.save_to_markdown("markdown content", self.pr_url)

    @patch.object(GitHubPRDiffExtractor, 'parse_pr_url')
    @patch.object(GitHubPRDiffExtractor, 'fetch_diff')
    @patch.object(GitHubPRDiffExtractor, 'generate_markdown')
    @patch.object(GitHubPRDiffExtractor, 'save_to_markdown')
    def test_extract_diff_success(self, mock_save, mock_generate, mock_fetch, mock_parse):
        """Test the entire diff extraction process."""
        mock_parse.return_value = (self.owner, self.repo, self.pr_number)
        mock_fetch.return_value = "diff_text"
        mock_generate.return_value = "markdown"
        mock_save.return_value = "/path/to/file.md"

        self.extractor.set_credentials(self.git_token, self.api_base_url)
        result_path = self.extractor.extract_diff(self.pr_url)

        mock_parse.assert_called_with(self.pr_url)
        mock_fetch.assert_called_with(self.owner, self.repo, self.pr_number)
        mock_generate.assert_called_with("diff_text", self.pr_url)
        mock_save.assert_called_with("markdown", self.pr_url)
        self.assertEqual(result_path, "/path/to/file.md")

    @patch.object(GitHubPRDiffExtractor, 'extract_diff', return_value=None)
    def test_extract_diff_failure_in_main(self, mock_extract_diff):
        """Test main function when extract_diff returns None."""
        with patch('sys.argv', ['get_pr_diff_from_github.py', self.pr_url]):
            main()
            mock_extract_diff.assert_called_once_with(self.pr_url)


class TestMainFunction(unittest.TestCase):

    @patch('sys.argv', ['script_name', 'some_pr_url'])
    @patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
    def test_main_success(self, mock_extractor_class):
        """Test the main function with valid arguments."""
        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract_diff.return_value = "/path/to/diff.md"
        mock_extractor_class.return_value = mock_extractor_instance

        main()

        mock_extractor_instance.extract_diff.assert_called_once_with('some_pr_url')

    @patch('sys.argv', ['script_name'])
    def test_main_invalid_args(self):
        """Test the main function with invalid arguments."""
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)

    @patch('sys.argv', ['script_name', 'some_pr_url'])
    @patch('get_pr_diff_from_github.GitHubPRDiffExtractor')
    def test_main_exception(self, mock_extractor_class):
        """Test the main function when an exception occurs."""
        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract_diff.side_effect = Exception("Test Error")
        mock_extractor_class.return_value = mock_extractor_instance

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
