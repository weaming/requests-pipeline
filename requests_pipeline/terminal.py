import subprocess


def get_terminal_size():
    rows, columns = subprocess.check_output(["stty", "size"]).split()
    return int(rows), int(columns)


TTY_ROWS, TTY_COLUMNS = get_terminal_size()
