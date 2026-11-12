"""Tests for csv_quote_checker: unbalanced quotes, CLI, examples, hygiene.

CWD-robust: every CLI run uses absolute paths and every assertion
checks a file-name suffix plus the message text, never an absolute
path — so this suite passes from any working directory.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import csv_quote_checker as checker

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "csv_quote_checker.py"
EXAMPLES = ROOT / "examples"
README = ROOT / "README.md"
GOAL_DIR = Path.home() / "workspace" / "goals" / "github-automation-business"

UNBALANCED = "unbalanced quote (a quote opens and never closes)"
AFTER_CLOSE = 'bad quoting: \',\' expected after \'"\''


def problems(text, delimiter=","):
    return [(p.path, p.line, p.reason)
            for p in checker.check_text(text, "t.csv", delimiter)]


def reasons(text, delimiter=","):
    return [(p.line, p.reason)
            for p in checker.check_text(text, "t.csv", delimiter)]


class TestUnbalancedQuotes(unittest.TestCase):
    def test_quote_never_closes(self):
        found = reasons('a,b\n1,"unclosed\n')
        self.assertEqual(found, [(2, UNBALANCED)])

    def test_quote_swallows_later_rows(self):
        found = reasons('a,b\n1,"x\n2,3\n4,5\n')
        self.assertEqual(found, [(2, UNBALANCED)])

    def test_reported_line_is_where_record_starts(self):
        found = reasons('a,b\n1,Alice,90\n2,"Bob,85\n3,Carol,88\n')
        self.assertEqual(found, [(3, UNBALANCED)])

    def test_quote_opens_on_last_line_no_newline(self):
        found = reasons('a,b\n1,"x')
        self.assertEqual(found, [(2, UNBALANCED)])

    def test_quote_opens_on_first_line(self):
        found = reasons('"a,b\n1,2\n')
        self.assertEqual(found, [(1, UNBALANCED)])

    def test_lone_quote_field(self):
        found = reasons('a,b\n1,",2\n')
        self.assertEqual(found, [(2, UNBALANCED)])

    def test_crlf_unclosed_quote(self):
        found = reasons('a,b\r\n1,"x\r\n')
        self.assertEqual(found, [(2, UNBALANCED)])

    def test_only_one_problem_per_broken_file(self):
        # The quote on line 2 swallows lines 3-4 into one field;
        # the file reports exactly one problem, at line 2.
        found = reasons('a,b\n1,"x\n2,3\n4,5\n')
        self.assertEqual(found, [(2, UNBALANCED)])

    def test_only_one_problem_after_close_error(self):
        # The first bad-quoting error stops the check of the file.
        found = reasons('a,b\n1,"abc"def,2\n3,"ghi"jkl,4\n')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0], (2, AFTER_CLOSE))


class TestBadQuoting(unittest.TestCase):
    def test_text_after_closing_quote(self):
        found = reasons('a,b\n1,"abc"def,2\n')
        self.assertEqual(found, [(2, AFTER_CLOSE)])

    def test_text_after_closing_quote_first_column(self):
        found = reasons('a,b\n"abc"def,2\n')
        self.assertEqual(found, [(2, AFTER_CLOSE)])

    def test_quote_then_space_then_delimiter(self):
        found = reasons('a,b\n1,"abc" ,2\n')
        self.assertEqual(found, [(2, AFTER_CLOSE)])


class TestCleanFiles(unittest.TestCase):
    def test_clean_file_passes(self):
        self.assertEqual(reasons("id,name,score\n1,Alice,90\n"), [])

    def test_quoted_field_with_comma_passes(self):
        self.assertEqual(
            reasons('id,name\n1,"Carol, Jr."\n'), [])

    def test_multiline_quoted_field(self):
        self.assertEqual(
            reasons('a,b\n"line one\nline two",2\n'), [])

    def test_doubled_quote_escape_passes(self):
        self.assertEqual(
            reasons('a,b\n1,"say ""hi""",2\n'), [])

    def test_header_only_file_passes(self):
        self.assertEqual(reasons("a,b,c\n"), [])

    def test_empty_file_passes(self):
        self.assertEqual(reasons(""), [])

    def test_ragged_rows_pass(self):
        # Column counts are repo #58's job, not this one.
        self.assertEqual(reasons("a,b\n1,2,3\n"), [])

    def test_blank_lines_pass(self):
        # Empty rows are repo #73's job, not this one.
        self.assertEqual(reasons("a,b\n1,2\n\n3,4\n"), [])

    def test_quote_in_unquoted_field_is_literal(self):
        # The csv module reads ab"cd as one field; this tool
        # does not flag it, and says so in the README.
        self.assertEqual(reasons('a,b\n1,ab"cd,3\n'), [])

    def test_clean_rows_before_broken_record_still_checked(self):
        found = reasons('a,b\n1,2\n3,"x\n')
        self.assertEqual(found, [(3, UNBALANCED)])


class TestEdgeCases(unittest.TestCase):
    def test_nul_byte_reported_once(self):
        found = reasons("a,b\n1,\x002\n")
        self.assertEqual(len(found), 1)
        self.assertIn("NUL", found[0][1])

    def test_custom_delimiter(self):
        found = reasons('a;b\n1;"x\n', delimiter=";")
        self.assertEqual(found, [(2, UNBALANCED)])

    def test_tab_delimiter(self):
        found = reasons('a\tb\n1\t"x\n', delimiter="\t")
        self.assertEqual(found, [(2, UNBALANCED)])

    def test_wrong_delimiter_misses_the_quote(self):
        # With commas, the semicolon file's lines are single
        # fields and the quote never opens one.
        self.assertEqual(reasons('a;b\n1;"x\n'), [])

    def test_problem_text_format(self):
        problem = checker.check_text('a,b\n1,"x\n', "f.csv")[0]
        self.assertEqual(problem.text(),
                         "f.csv:2: " + UNBALANCED)

    def test_problem_as_dict(self):
        problem = checker.check_text('a,b\n1,"x\n', "f.csv")[0]
        self.assertEqual(problem.as_dict(), {
            "file": "f.csv", "line": 2, "reason": UNBALANCED,
        })


class TestCheckFile(unittest.TestCase):
    def test_unreadable_path(self):
        found = checker.check_file("/nonexistent-dir-xyz/f.csv")
        self.assertEqual(len(found), 1)
        self.assertIn("cannot read file", found[0].reason)

    def test_file_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            path.write_text('a,b\n1,"x\n')
            found = checker.check_file(str(path))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].line, 2)
            self.assertEqual(found[0].reason, UNBALANCED)


class TestCollection(unittest.TestCase):
    def test_folder_walk_finds_csv_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.csv").write_text("a,b\n1,2\n")
            (root / "b.txt").write_text('a,b\n1,"x\n')
            (root / "sub").mkdir()
            (root / "sub" / "c.csv").write_text('a,b\n1,"x\n')
            files, missing = checker.collect_files([str(root)])
            self.assertEqual(missing, [])
            self.assertEqual(
                files, [str(root / "a.csv"), str(root / "sub" / "c.csv")])

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "x.csv").write_text('a,b\n1,"x\n')
            (root / "a.csv").write_text("a,b\n1,2\n")
            files, _ = checker.collect_files([str(root)])
            self.assertEqual(files, [str(root / "a.csv")])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.csv").write_text("a,b\n1,2\n")
            (root / "sub").mkdir()
            (root / "sub" / "b.csv").write_text("a,b\n1,2\n")
            files, _ = checker.collect_files([str(root)], recursive=False)
            self.assertEqual(files, [str(root / "a.csv")])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "draft-a.csv").write_text("a,b\n1,2\n")
            (root / "final.csv").write_text("a,b\n1,2\n")
            files, _ = checker.collect_files(
                [str(root)], exclude=["draft-*"])
            self.assertEqual(files, [str(root / "final.csv")])

    def test_direct_file_checked_despite_exclude_and_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "draft-data.txt"
            target.write_text('a,b\n1,"x\n')
            files, _ = checker.collect_files(
                [str(target)], exclude=["draft-*"])
            self.assertEqual(files, [str(target)])

    def test_missing_path_reported(self):
        files, missing = checker.collect_files(["/no-such-path-xyz"])
        self.assertEqual(files, [])
        self.assertEqual(missing, ["/no-such-path-xyz"])

    def test_uppercase_extension_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "UP.CSV").write_text("a,b\n1,2\n")
            files, _ = checker.collect_files([str(root)])
            self.assertEqual(files, [str(root / "UP.CSV")])

    def test_results_sorted_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.csv").write_text("a,b\n1,2\n")
            (root / "a.csv").write_text("a,b\n1,2\n")
            files, _ = checker.collect_files(
                [str(root / "b.csv"), str(root), str(root / "a.csv")])
            self.assertEqual(files, [str(root / "a.csv"),
                                     str(root / "b.csv")])


class TestCLI(unittest.TestCase):
    def run_cli(self, *args, stdin=None, cwd=None):
        return subprocess.run(
            [sys.executable, str(SRC), *args],
            input=stdin, capture_output=True, text=True, cwd=cwd,
        )

    def test_clean_file_exit_0(self):
        result = self.run_cli(str(EXAMPLES / "good.csv"))
        self.assertEqual(result.returncode, 0)
        self.assertIn("good.csv: OK", result.stdout)
        self.assertIn("no unbalanced quotes", result.stdout)

    def test_bad_file_exit_1(self):
        result = self.run_cli(str(EXAMPLES / "unclosed.csv"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("unclosed.csv:3: " + UNBALANCED, result.stdout)

    def test_after_close_exit_1(self):
        result = self.run_cli(str(EXAMPLES / "after-close.csv"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("after-close.csv:2: " + AFTER_CLOSE, result.stdout)

    def test_folder_exit_1_and_summary(self):
        result = self.run_cli(str(EXAMPLES))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checked 4 file(s), 2 problem(s) in 2 file(s).",
                      result.stdout)

    def test_no_args_exit_2(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)

    def test_missing_path_exit_2(self):
        result = self.run_cli("no-such-file.csv")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such file or folder", result.stderr)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(tmp)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no CSV files found", result.stderr)

    def test_bad_delimiter_exit_2(self):
        result = self.run_cli("--delimiter", ";;",
                              str(EXAMPLES / "good.csv"))
        self.assertEqual(result.returncode, 2)

    def test_bad_flag_exit_2(self):
        result = self.run_cli("--nope", str(EXAMPLES / "good.csv"))
        self.assertEqual(result.returncode, 2)

    def test_delimiter_flag(self):
        result = self.run_cli("--delimiter", ";",
                              str(EXAMPLES / "semicolon.csv"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("semicolon.csv:3: " + UNBALANCED, result.stdout)

    def test_stdin(self):
        result = self.run_cli("--stdin", stdin='a,b\n1,"x\n')
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL <stdin>:2: " + UNBALANCED, result.stdout)

    def test_stdin_clean(self):
        result = self.run_cli("--stdin", stdin="a,b\n1,2\n")
        self.assertEqual(result.returncode, 0)

    def test_stdin_with_path_exit_2(self):
        result = self.run_cli("--stdin", str(EXAMPLES / "good.csv"))
        self.assertEqual(result.returncode, 2)

    def test_json_output(self):
        result = self.run_cli("--json",
                              str(EXAMPLES / "unclosed.csv"))
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 1)
        self.assertEqual(payload["summary"]["checked"], 1)
        self.assertTrue(payload["files"][0]["file"]
                        .endswith("unclosed.csv"))
        self.assertEqual(payload["files"][0]["problems"][0]["line"], 3)
        self.assertEqual(payload["files"][0]["problems"][0]["reason"],
                         UNBALANCED)
        self.assertIn("Checked 1 file(s), 1 problem(s)",
                      result.stderr)

    def test_json_clean(self):
        result = self.run_cli("--json", str(EXAMPLES / "good.csv"))
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 0)

    def test_version(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)

    def test_exclude_flag(self):
        result = self.run_cli("--exclude", "unclosed.csv",
                              str(EXAMPLES))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("unclosed", result.stdout)
        self.assertIn("after-close", result.stdout)


class TestCwdRobustness(unittest.TestCase):
    """The CLI works from any working directory (Nov 11 lesson)."""

    def test_cli_from_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SRC),
                 str(EXAMPLES / "unclosed.csv")],
                capture_output=True, text=True, cwd=tmp,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("unclosed.csv:3: " + UNBALANCED, result.stdout)

    def test_cli_from_goal_dir(self):
        result = subprocess.run(
            [sys.executable, str(SRC), str(EXAMPLES / "good.csv")],
            capture_output=True, text=True, cwd=str(GOAL_DIR),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("good.csv: OK", result.stdout)

    def test_cli_from_tmp_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SRC), str(EXAMPLES)],
                capture_output=True, text=True, cwd=tmp,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checked 4 file(s), 2 problem(s) in 2 file(s).",
                      result.stdout)


class TestExamples(unittest.TestCase):
    def test_bundled_files_expected_problems(self):
        expected = {
            "good.csv": [],
            "unclosed.csv": [(3, UNBALANCED)],
            "after-close.csv": [(2, AFTER_CLOSE)],
        }
        for name, want in expected.items():
            text = (EXAMPLES / name).read_text()
            got = [(p.line, p.reason)
                   for p in checker.check_text(text, name)]
            self.assertEqual(got, want, name)

    def test_semicolon_file_with_delimiter(self):
        text = (EXAMPLES / "semicolon.csv").read_text()
        got = [(p.line, p.reason)
               for p in checker.check_text(text, "semicolon.csv",
                                           delimiter=";")]
        self.assertEqual(got, [(3, UNBALANCED)])

    def test_semicolon_file_default_delimiter_passes(self):
        text = (EXAMPLES / "semicolon.csv").read_text()
        got = [(p.line, p.reason)
               for p in checker.check_text(text, "semicolon.csv")]
        self.assertEqual(got, [])

    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", str(EXAMPLES / "run-example.sh")],
            capture_output=True, text=True, cwd="/tmp",
        )
        self.assertEqual(result.returncode, 0)
        sample = (EXAMPLES / "sample-output.md").read_text()
        block = sample.split("```\n")[1]
        self.assertEqual(result.stdout, block)

    def test_readme_quoted_outputs_are_real(self):
        readme = README.read_text()
        for line in [
            "examples/good.csv: OK",
            "OK — 1 file(s) checked, no unbalanced quotes.",
            "FAIL examples/unclosed.csv:3: " + UNBALANCED,
            "FAIL examples/after-close.csv:2: " + AFTER_CLOSE,
            "FAIL examples/semicolon.csv:3: " + UNBALANCED,
            "Checked 4 file(s), 2 problem(s) in 2 file(s).",
            "FAIL <stdin>:3: " + UNBALANCED,
        ]:
            self.assertIn(line, readme, line)


class TestHygiene(unittest.TestCase):
    def test_no_placeholder_text(self):
        banned = ["TODO", "FIXME", "XXX", "coming soon", "lorem"]
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace")
            for word in banned:
                self.assertNotIn(word, text,
                                 f"{word} in {path.relative_to(ROOT)}")

    def test_no_absolute_paths(self):
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace")
            self.assertNotIn("/home/hatch", text,
                             f"absolute path in {path.relative_to(ROOT)}")
            self.assertNotIn("/Users/", text,
                             f"absolute path in {path.relative_to(ROOT)}")
            self.assertNotIn("/tmp/", text,
                             f"absolute path in {path.relative_to(ROOT)}")

    def test_stdlib_only_imports(self):
        allowed_src = {
            "argparse", "csv", "fnmatch", "io", "json", "os", "sys",
            "pathlib",
        }
        allowed_tests = allowed_src | {
            "ast", "json", "subprocess", "tempfile", "unittest",
            "csv_quote_checker",
        }
        for path, allowed in [(SRC, allowed_src),
                              (Path(__file__), allowed_tests)]:
            tree = ast.parse(path.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported.add(node.module.split(".")[0])
            self.assertTrue(imported <= allowed,
                            f"{path.name} imports non-stdlib: "
                            f"{imported - allowed}")
            self.assertNotIn("yaml", imported)

    def test_no_yaml_anywhere_in_source(self):
        text = SRC.read_text()
        self.assertNotIn("yaml", text)

    def test_no_secrets_in_repo(self):
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace").lower()
            for marker in ["api_key", "api-key", "password =", "secret ="]:
                self.assertNotIn(marker, text,
                                 f"possible secret in {path.relative_to(ROOT)}")

    def test_gitignore_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("test_csv_quote_checker.py", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)


if __name__ == "__main__":
    unittest.main()
