# Sample output

Output of `sh examples/run-example.sh` — the checker run over the
whole `examples/` folder (4 files, 2 problems in 2 files):

```
FAIL examples/after-close.csv:2: bad quoting: ',' expected after '"'
examples/good.csv: OK
examples/semicolon.csv: OK
FAIL examples/unclosed.csv:3: unbalanced quote (a quote opens and never closes)
Checked 4 file(s), 2 problem(s) in 2 file(s).
```

`examples/semicolon.csv` passes here because it is checked with
the default comma delimiter — with commas, each line is a single
field and the quote on line 3 never opens a quoted field. Run it
with `--delimiter ';'` to check it properly (see the README).
