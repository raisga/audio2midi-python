import unittest
from click.testing import CliRunner
from main import cli

class TestCLI(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_no_args(self):
        result = self.runner.invoke(cli)
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Usage:', result.output)

    def test_help_flag(self):
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Show this help message and exit', result.output)

    def test_hello_command(self):
        result = self.runner.invoke(cli, ['hello'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Hello world!', result.output)

if __name__ == '__main__':
    unittest.main()
