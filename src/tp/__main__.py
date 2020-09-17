from __future__ import annotations

import codecs
import functools
import io
import operator
import os
import re
import sys
from pathlib import Path

import attrs
import click
from columnar import columnar

import tp


@attrs.define(auto_attribs=True)
class IndexMatcher:
    idx: int
    pattern: re.Pattern
    inverse: bool

    @classmethod
    def from_str(cls, s: str):
        s = s.replace(r"\:", placeholder := "IndexMatcher<ESCAPED_DOUBLE_DOT>")
        idx, regex, *raw_flags = s.split(":")
        regex = regex.replace(placeholder, ":")

        inverse = False
        flags = []
        for rf in raw_flags:
            rf = rf.upper()
            if rf == "V":
                inverse = True
            else:
                flags.append(getattr(re, rf))

        pattern = re.compile(regex, functools.reduce(operator.ior, flags, 0))
        return cls(idx=int(idx), pattern=pattern, inverse=inverse)

    def __call__(self, sequence: list[str]) -> bool:
        x = sequence[self.idx]
        match = self.pattern.search(x)
        return not match if self.inverse else bool(match)


class IndexRegexes(list):
    name: str = "IndexRegex"

    class ParamType(click.ParamType):
        name: str = "IndexRegex"

        def convert(
            self,
            value: str | IndexRegexes,
            param: click.Parameter | None,
            ctx: click.Context | None,
        ) -> IndexRegexes:
            if isinstance(value, str):
                try:
                    return IndexRegexes([IndexMatcher.from_str(x) for x in value.split(",")])
                except Exception as exc:
                    self.fail(f"{exc.__class__.__name__}: {exc}")


def split_stream(stream: io.TextIOBase, *, sep: str):
    buffer = ""
    for line in stream:
        buffer += line
        if (idx := buffer.find(sep)) != -1:
            if s := buffer[:idx]:
                yield s
            yield sep
            buffer = buffer[idx + len(sep) :]
    if buffer:
        yield buffer


def str_to_slice(s: str):
    args = [eval(x) if x else None for x in s.split(":")]
    return slice(*args)

@click.command()
@click.option(
    "-i", "--input", "stdin", type=click.File("rb"), default=sys.stdin, show_default="/dev/stdin"
)
@click.option(
    "-o",
    "--output",
    "stdout",
    type=click.File("wb"),
    default=sys.stdout,
    show_default="/dev/stdout",
)
@click.option("-l", "--max-lines-per-row", default=1, show_default=True)
@click.option(
    "-b", "--borders", default=False, is_flag=True, show_default=True, help="Show table borders"
)
@click.option(
    "-i",
    "--row-slice",
    "r_slice_or_i",
    default="0:",
    show_default=True,
    help="A python slice or a index",
)
@click.option(
    "-j",
    "--column-slice",
    "c_slice_or_j",
    default="0:",
    show_default=True,
    help="A python slice or a index",
)
@click.option(
    "-h",
    "--header-pattern",
    default=r"\S+(?: \S+)*",
    show_default=True,
    help="""
Pattern to match a header. (used with python's re.findall(pattern, raw_header))

Return a list of all non-overlapping matches in the string.

If one or more capturing groups are present in the pattern, return
a list of groups; this will be a list of tuples if the pattern
has more than one group.

Empty matches are included in the result.
""".strip(),
)
@click.option(
    "-r",
    "--row-pattern",
    default=r"\S+(?: \S+)*",
    show_default=True,
    help="""
Pattern to match a row. (used with python's re.findall(pattern, raw_row))

Return a list of all non-overlapping matches in the string.

If one or more capturing groups are present in the pattern, return
a list of groups; this will be a list of tuples if the pattern
has more than one group.

Empty matches are included in the result.
""".strip(),
)
@click.option(
    "-v", "--verbose", default=False, is_flag=True, help="Output verbose info in /dev/stderr"
)
@click.option(
    "--sep",
    default=r"\x1b[2J\x1b[H",
    show_default=True,
    callback=lambda _, __, sep: codecs.decode(sep.encode(), "unicode-escape"),
    help="Stream separator",
)
@click.option(
    "-z",
    "--hide-header",
    default=False,
    show_default=True,
    is_flag=True,
    help="Parse but hide header",
)
@click.option(
    "-f",
    "--row-filter",
    default=None,
    show_default=True,
    help=r"""
Filter row values using regex.

INDEXREGEXES -> index:regex[:flags],[index:regex[:flags]]...

: should be escaped as \:
""".strip(),
    type=IndexRegexes.ParamType(),
)
@click.option(
    "--completion",
    default=False,
    show_default=True,
    is_flag=True,
    help="Output shell completion"
)
def main(
    stdin: io.TextIOBase,
    stdout: io.TextIOBase,
    max_lines_per_row: int,
    borders: bool,
    r_slice_or_i: str,
    c_slice_or_j: str,
    row_pattern: str,
    header_pattern: str,
    verbose: bool,
    sep: str,
    hide_header: bool,
    row_filter: list[IndexMatcher] | None,
    completion: bool
) -> int:
    if completion:
        shell = Path(os.environ.get("SHELL", "/bin/bash"))
        if shell.name == "bash":
            os.environ.setdefault("_TP_COMPLETE", "bash_source")
        elif shell.name == "zsh":
            os.environ.setdefault("_TP_COMPLETE", "zsh_source")
        elif shell.name == "fish":
            os.environ.setdefault("_TP_COMPLETE", "fish_source")
        else:
            raise SystemError(f"Unsupported {shell=!r}")
        main.main()

    r_slice_or_i = str_to_slice(r_slice_or_i) if ":" in r_slice_or_i else int(r_slice_or_i)
    c_slice_or_j = str_to_slice(c_slice_or_j) if ":" in c_slice_or_j else int(c_slice_or_j)

    header_pattern = re.compile(header_pattern)
    row_pattern = re.compile(row_pattern)

    iterations = 0
    for lines in split_stream(stdin, sep=sep):
        if lines == sep:
            print(file=stdout, end=sep)
            continue

        lines = [line for line in lines.split("\n") if line.strip()]
        if len(lines) == 0:
            lines = ["NO HEADERS", "NO ROWS"]
        if len(lines) == 1:
            lines = lines + ["NO ROWS"]

        header, *rows = lines
        header = header_pattern.findall(header)
        rows = [row_pattern.findall(row) for row in rows]

        if row_filter is not None:
            rows = [row for row in rows if all(matcher(row) for matcher in row_filter)]

        if verbose:
            print(f"{header=!r}", file=sys.stderr)
            for i, row in enumerate(rows):
                print(f"{i=!r}, {row=!r}", file=sys.stderr)

        data = []
        for x in [rows[r_slice_or_i]] if isinstance(r_slice_or_i, int) else rows[r_slice_or_i]:
            diff = len(header) - len(x)
            if diff > 0:
                x.extend("tp:NOTFOUND" for _ in range(diff))
            elif diff < 0:
                x = x[:diff]

            data.append([x[c_slice_or_j]] if isinstance(c_slice_or_j, int) else x[c_slice_or_j])

        header = [header[c_slice_or_j]] if isinstance(c_slice_or_j, int) else header[c_slice_or_j]
        if data:
            table = columnar(
                data,
                None if hide_header else header,
                no_borders=not borders,
                column_sep=" | ",
                wrap_max=max_lines_per_row - 1,
            )
            print(table, file=stdout, end="")

        elif not hide_header:
            table = columnar(
                [["tp:NOTFOUND" for _ in header]],
                None if hide_header else header,
                no_borders=not borders,
                column_sep=" | ",
                wrap_max=max_lines_per_row - 1,
            )
            print(table, file=stdout, end="")

        iterations += 1

    if iterations == 1:
        print(file=stdout)

    return 0


def run():
    return main(auto_envvar_prefix=tp.__name__.upper())


if __name__ == "__main__":
    exit_code = run()
    exit(exit_code)
