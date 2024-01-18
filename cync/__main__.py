"""Listens for file changes and makes the moves.

Does only file sync only.
"""

import logging
import os
import time

import click
from watchdog.observers import Observer

from cync.handler import ScpGitEventHandler


@click.command(
    name="cync",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("path")
@click.argument(
    "targets",
    nargs=-1,
    required=False,
)
@click.option(
    "--extensions", "-e", default="j2,py,sh,yml,json,yaml,txt,md,toml,conf,service"
)
@click.option("--create-if-missing", "-c", is_flag=True)
@click.option("--reset-targets", is_flag=True)
def cync(
    path: str,
    targets: list[str],
    extensions: str,
    create_if_missing: bool,
    reset_targets: bool,
):
    """cync, a tool for syncing between nodes.

    Example usage: cync . computelab:/home/scratch.npengra_sw/computelab/
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    targets = list(targets)
    for i, t in enumerate(targets):
        if t == "c":  # shortcut c to a common path
            targets[i] = "computelab:/home/scratch.npengra_sw/computelab/"

    # Default "." to current directory
    if path == ".":
        path = os.getcwd()
    if not path.endswith("/"):
        path += "/"

    event_handler = ScpGitEventHandler(
        extensions=extensions,
        host_directory=path,
        targets=list(targets),
        initial_branch="",
        initial_commit="",
    )

    if create_if_missing:
        event_handler.ssh_mkdir(targets[0].split(":", 1)[-1])

    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)

    if reset_targets:
        event_handler.reset_targets()

    observer.start()
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()
        event_handler.close()


if __name__ == "__main__":
    cync()
