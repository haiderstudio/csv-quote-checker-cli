# csv-quote-checker-cli

Check CSV files for unbalanced quotes, fail CI when any are found.

[![CI](https://github.com/haiderstudio/csv-quote-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/csv-quote-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`csv_quote_checker` reads each CSV file you point it at and
reports every broken record, with the file and the line where
the record starts:

- An unbalanced quote is a quote that opens and never closes —
  the rest of the file becomes one field. One stray quote in a
  CSV swallows every row after it, and the import fails (or
  worse, silently imports garbage). This tool reports the line
  where the broken record starts, so you can find the stray
  quote at once. The `unclosed.csv` example has its quote open
  on line 3 and never close — lines 3, 4, and 5 all become one
  field, and the tool reports line 3.
- A quote that closes and is followed by other characters
  before the next comma — `"Alice"extra` — is also a quoting
  problem, and is reported the same way. The `after-close.csv`
  example shows it.
- It exits 1 when any quoting problem is found, so it can fail
  a CI run. A clean folder exits 0.
- The check is done with Python's `csv` module in strict mode:
  an unbalanced quote raises an error, and that error is the
  whole mechanism. A quoted field that spans several lines (an
  address with a line break inside quotes, for example) is
  valid CSV and passes, and a doubled quote (`""`) inside a
  quoted field is the normal way to write one quote, so it
  passes too — the `good.csv` example has both and passes
  clean.
- CSV files come from the command line (one or more), or from a
  folder walk: every `.csv` file under a folder, recursively by
  default (`--no-recursive` stops at the top level). `.git` and
  `__pycache__` folders are never walked, and directory links
  are never followed, so a link cycle cannot loop the check.
- `--delimiter` sets the field separator, for example
  `--delimiter ';'` for semicolon files. A file checked with
  the wrong delimiter is not an error — it is just checked as
  one-field rows — so pick the delimiter your files use.
- `--exclude PATTERN` skips walked files by glob, for example
  `--exclude 'draft-*'`. It can be repeated. A file passed
  directly on the command line is always checked, even if it
  matches an exclude pattern and even if it has no `.csv`
  extension.
- `--stdin` reads one CSV document from standard input.
- `--json` prints the result as machine-readable JSON (the
  summary goes to standard error, so standard output stays
  clean JSON).
- It is report-only and runs fully offline: it never edits a
  file, sends nothing anywhere, and needs no API key. Python
  standard library only — the `csv` module does the parsing.

## What it does NOT do

- It does not check column counts — that is repo #58's
  `csv-column-count-checker-cli`. A row with the wrong number
  of columns but no quoting problem passes here.
- It does not check empty rows or empty cells — that is repo
  #73's `csv-empty-checker-cli`. A blank line passes here.
- It does not check the header row's names or duplicates —
  that is repo #40's `csv-header-checker-cli`.
- It does not flag a quote in the middle of an unquoted field
  (for example `ab"cd`). Python's `csv` module reads that
  quote as part of the field, so the check cannot see it.
  That is a limit of this tool, stated plainly.
- It does not fix a broken quote. An unbalanced quote is
  reported; deciding where the quote should close is your job.
- The first broken record stops the check of that file — an
  unbalanced quote swallows the rest of the file anyway, so
  there is nothing useful left to check after it.
- An empty file passes: it has no quotes to be unbalanced.

## Who it is for

Anyone who ships CSV data files and wants them to parse
before they are imported: a data analyst checking a
spreadsheet export, a developer adding a CI step that fails
the build when a data file has a broken quote, or anyone
tidying a folder of CSVs before they go into a database. One
stray quote is invisible in the file itself — this catches
it before the import does.

## How this differs from similar tools

The exact name `csv-quote-checker-cli` matches 0
repositories on GitHub (checked Nov 11, 2026), and the
wider field is small: `csv quote checker` matches 3
repositories. The top ones are
cart231-ffly-b/jp-csv-traps-free, 0 stars — Japanese CSV
test files with quoted newlines (test data, not a checker);
livastic-vm3-primary-tmp-260920/defi-payment-proof-qa,
0 stars — a USDC ledger with a "quote checker" (a different
job, checking prices, not CSV quotes); and
ManojKumarPatnaik/Major-project-list, 261 stars — a list of
practice projects (noise). No rival checks CSV quotes. None
of them is a tested Python CLI that checks CSV files for
unbalanced quotes as its one job, reports each broken record
with file and line, and exits 1 for CI. This tool does
that one job: a Python standard-library-only CLI that checks
CSV files for unbalanced quotes — no install beyond Python,
no website, no network.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/csv-quote-checker-cli.git
cd csv-quote-checker-cli
python3 src/csv_quote_checker.py examples/good.csv
```

```
examples/good.csv: OK
OK — 1 file(s) checked, no unbalanced quotes.
```

## Usage

Check one clean file (quoted commas, doubled quotes, and a
multi-line quoted field all pass):

```
python3 src/csv_quote_checker.py examples/good.csv
```

```
examples/good.csv: OK
OK — 1 file(s) checked, no unbalanced quotes.
```

Check a file with an unbalanced quote (the quote opens on line
3 and never closes, swallowing lines 3–5 into one field):

```
python3 src/csv_quote_checker.py examples/unclosed.csv
```

```
FAIL examples/unclosed.csv:3: unbalanced quote (a quote opens and never closes)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Check a file with text after a closing quote:

```
python3 src/csv_quote_checker.py examples/after-close.csv
```

```
FAIL examples/after-close.csv:2: bad quoting: ',' expected after '"'
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Check a semicolon file — first without the flag, then with it.
Without `--delimiter ';'` the lines are read as single fields
and the quote on line 3 never opens a quoted field:

```
python3 src/csv_quote_checker.py examples/semicolon.csv
```

```
examples/semicolon.csv: OK
OK — 1 file(s) checked, no unbalanced quotes.
```

```
python3 src/csv_quote_checker.py --delimiter ';' examples/semicolon.csv
```

```
FAIL examples/semicolon.csv:3: unbalanced quote (a quote opens and never closes)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Check a whole folder:

```
python3 src/csv_quote_checker.py examples/
```

```
FAIL examples/after-close.csv:2: bad quoting: ',' expected after '"'
examples/good.csv: OK
examples/semicolon.csv: OK
FAIL examples/unclosed.csv:3: unbalanced quote (a quote opens and never closes)
Checked 4 file(s), 2 problem(s) in 2 file(s).
```

Check one document from standard input:

```
python3 src/csv_quote_checker.py --stdin < examples/unclosed.csv
```

```
FAIL <stdin>:3: unbalanced quote (a quote opens and never closes)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/csv_quote_checker.py --json examples/unclosed.csv
```

```
{
  "files": [
    {
      "file": "examples/unclosed.csv",
      "problems": [
        {
          "file": "examples/unclosed.csv",
          "line": 3,
          "reason": "unbalanced quote (a quote opens and never closes)"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "files_with_problems": 1,
    "problems": 1
  }
}
```

Exit codes: 0 when every checked file is clean, 1 when any
quoting problem is found, 2 for a usage problem (no files
given, a bad flag, a bad `--delimiter` value, or a missing
file or folder).

## Examples

### 1. A folder of data files, default comma delimiter

`examples/` holds four CSV files. One passes, two fail, and
the semicolon file passes only because it is checked with
the wrong delimiter — run it with `--delimiter ';'` to check
it properly:

```
python3 src/csv_quote_checker.py examples/
```

```
FAIL examples/after-close.csv:2: bad quoting: ',' expected after '"'
examples/good.csv: OK
examples/semicolon.csv: OK
FAIL examples/unclosed.csv:3: unbalanced quote (a quote opens and never closes)
Checked 4 file(s), 2 problem(s) in 2 file(s).
```

### 2. The semicolon file, checked properly

```
python3 src/csv_quote_checker.py --delimiter ';' examples/semicolon.csv
```

```
FAIL examples/semicolon.csv:3: unbalanced quote (a quote opens and never closes)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks the whole `examples/` folder (fail, on
purpose — it picks up the unbalanced quote and the text
after a closing quote). Its full output is in
`examples/sample-output.md`, ending with `Checked 4 file(s),
2 problem(s) in 2 file(s).` The failing run exits 1, which
is the expected result — the script ends with exit 0 so it
can be run as a demo.

## How it is tested

Tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_csv_quote_checker.py
```

The tests cover: unbalanced quotes (a quote that never
closes, a quote that swallows later rows, a quote that
opens on the last line with no newline, the line number
reported is the line where the record starts, CRLF line
endings), bad quoting (text after a closing quote, a quote
that closes then has more text before the delimiter), clean
files (quoted fields with commas, multi-line quoted fields,
doubled quotes, a header-only file, an empty file, ragged
rows), edge cases (NUL bytes, a custom delimiter, a
tab-delimited file, a quote in the middle of an unquoted
field — read as part of the field, not flagged), file
collection (a good file, a missing path, a folder walk,
`.git` skipped, `--no-recursive`, `--exclude`, a direct file
checked even without a `.csv` extension and even if
excluded, an empty folder, uppercase `.CSV` extensions),
the CLI (exit 0/1/2, each flag, `--stdin` good and bad,
`--json` output, `--version`, bad flags, a bad delimiter,
missing paths, a folder summary count, and every bundled
example file read back with its expected problems), the
bundled examples (sample output compared byte-for-byte
against a fresh run, and the README-quoted outputs checked
against it), working-directory robustness (the tests pass from the repo root, from a
temp folder, and from the goal folder — paths are checked by file name
and message, never by an absolute path), and hygiene checks (no placeholder text, no
absolute paths, stdlib imports only, `.env` first in
`.gitignore`, CI file runs the test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea
of checking CSV files for quoting problems is not new — the
similar tools named above (the Japanese CSV test files, the
USDC ledger) are listed in "How this differs" — but every
line of code here is original, and the tool builds on
nothing but Python's standard library.
