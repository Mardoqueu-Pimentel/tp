import io
import re
import sys

import click
from columnar import columnar


@click.command()
@click.option(
	'-i', '--input',
	type=click.File('rb'), default=sys.stdin, show_default='/dev/stdin'
)
@click.option(
	'-o', '--output',
	type=click.File('wb'), default=sys.stdout, show_default='/dev/stdout'
)
@click.option(
	'-l', '--max-lines-per-row',
	default=1, show_default=True
)
@click.option(
	'-b', '--borders',
	default=False, is_flag=True, show_default=True,
	help='Show table borders'
)
@click.option(
	'-s', '--slice', 'slice_str',
	default='0:', show_default=True,
	help='A python slice'
)
def main(
		input: io.TextIOBase, output: io.TextIOBase,
		max_lines_per_row: int, borders: bool, slice_str: str) -> int:

	slices = slice(*(eval(x) if x else None for x in slice_str.split(':')))

	row_pattern = re.compile(r'\S+')
	rows = [row_pattern.findall(line) for line in input if line.strip()]
	if not rows:
		rows.append([])
	header, *rows = rows

	if not header:
		header.append('NO HEADERS')
	if not rows:
		rows.append(['NO ROWS'])

	table = columnar(
		rows[slices],
		header,
		no_borders=not borders,
		wrap_max=max_lines_per_row - 1
	)

	print(table, file=output)

	return 0


def run():
	return main(auto_envvar_prefix='TP')


if __name__ == '__main__':
	exit_code = run()
	exit(exit_code)
