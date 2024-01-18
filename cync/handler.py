""""""

from collections import defaultdict
import logging
from pathlib import Path

import git
from paramiko import AutoAddPolicy, SSHClient, SSHConfig
from scp import SCPClient
from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)


class ScpGitEventHandler(FileSystemEventHandler):
    """Updates the changed file on the target machine."""

    def __init__(
        self,
        host_directory: str,
        targets: list[str],
        extensions: str,
        initial_commit: str,
        initial_branch: str,
    ):
        super().__init__()
        self.host_directory = host_directory
        self.targets = targets
        self.logger = logging.root

        self._extensions = tuple((_.strip() for _ in extensions.split(",") if _))
        self._ssh_clients: dict[str, SSHClient] = {}
        self._scp_clients: dict[str, SCPClient] = {}
        self._dirs_exists_on_targets: dict[str, set[str]] = defaultdict(set)

        self._current_commit = initial_commit
        self._current_branch = initial_branch
        self._ignore_everything = False

    def _on_git_event(self, event: FileSystemEvent):
        return

    def reset_targets(self):
        """Git remote reset."""
        repo = git.Repo(self.host_directory)

        if (current_branch := str(repo.active_branch)) != self._current_branch:
            self.logger.info(
                "Git branch changed from %s to %s, updating targets",
                current_branch,
                self._current_branch,
            )
            self._ignore_everything = True
            # Push on this side
            repo.remote().push(force=True).raise_if_error()

            # Pull on the other side
            self._ssh_cmd(
                " && ".join(
                    [
                        "git fetch --all",
                        "git stash",
                        f"git checkout {current_branch}",
                        f"git reset --hard origin/{current_branch}",
                        "git clean -f",
                    ]
                )
            )

            # Upload untracked files
            for untracked_file in repo.untracked_files:
                self._scp_file(FileCreatedEvent(untracked_file))

            self._ignore_everything = False
            self._current_branch = current_branch

    def _is_git_path(self, event: FileSystemEvent):
        return ".git" in event.src_path

    def on_moved(self, event: FileMovedEvent):
        if self._is_git_path(event):
            self._on_git_event(event)
        if self._is_bad_path(event) or self._ignore_everything:
            self.logger.debug("Skipping %s", event.src_path)
            return

        self.on_deleted(FileDeletedEvent(event.src_path))
        self.on_created(FileCreatedEvent(event.dest_path))

    def on_created(self, event: FileCreatedEvent):
        if self._is_git_path(event):
            self._on_git_event(event)
        if self._is_bad_path(event) or self._ignore_everything:
            self.logger.debug("Skipping %s", event.src_path)
            return

        if event.is_directory:
            self.ssh_mkdir(event)
        else:
            self._scp_file(event)

    def on_deleted(self, event: FileDeletedEvent):
        if self._is_git_path(event):
            self._on_git_event(event)
        if self._is_bad_path(event) or self._ignore_everything:
            self.logger.debug("Skipping %s", event.src_path)
            return

        self._ssh_rm(event)

    def on_modified(self, event: FileModifiedEvent):
        if self._is_git_path(event):
            self._on_git_event(event)
        if self._is_bad_path(event) or self._ignore_everything:
            self.logger.debug("Skipping %s", event.src_path)
            return

        if not event.is_directory:
            self._scp_file(event)
        else:
            self.logger.debug("Skipping modified %s (directory)", event.src_path)

    def _is_bad_path(self, event: FileSystemEvent) -> bool:
        is_good_path = str(event.src_path).endswith(self._extensions)

        return not is_good_path or any(
            (
                ".pyc" in event.src_path,
                ".env/" in event.src_path,
                "__pycache__" in event.src_path,
                ".egg" in event.src_path,
            )
        )

    def _ssh_cmd(self, command: str):
        for target in self.targets:
            if ":" in target:
                user_and_domain, host_parent_dir = target.split(":", 1)
            else:
                user_and_domain, host_parent_dir = "titan@localhost", target
            if "@" in user_and_domain:
                user, domain = user_and_domain.split("@", 1)
            else:
                user = None
                domain = user_and_domain

            self.logger.debug(
                'Executing (as %s) "%s" -> %s',
                (user or "self"),
                command,
                domain,
            )

            ssh_client = self._get_ssh_client(domain)
            command = f"cd {host_parent_dir} && {command}"
            if user:
                ssh_client.exec_command(f'sudo su {user} bash -c "{command}"')

            ssh_client.exec_command(command)

    def _ssh_rm(self, event: FileDeletedEvent):
        recursion_flag = "r" if event.is_directory else ""
        for target in self.targets:
            user_and_domain, host_parent_dir = target.split(":", 1)
            if "@" in user_and_domain:
                user, domain = user_and_domain.split("@", 1)
            else:
                user = None
                domain = user_and_domain

            relative_src_path = str(event.src_path).replace(self.host_directory, "")
            target_path = str(Path(host_parent_dir) / relative_src_path)
            self.logger.info(
                "SSH rm -%sf %s -> %s:%s",
                recursion_flag,
                event.src_path,
                domain,
                target_path,
            )

            ssh_client = self._get_ssh_client(domain)
            command = f"rm -{recursion_flag}f {target_path}"
            if user:
                ssh_client.exec_command(f'sudo su {user} bash -c "{command}"')
            ssh_client.exec_command(command)

    def ssh_mkdir(
        self, event: FileModifiedEvent | FileCreatedEvent | FileMovedEvent | str
    ):
        """Create a directory at the specified location."""
        assert isinstance(event, str) or event.is_directory, event.src_path

        src_path: str = event if isinstance(event, str) else event.src_path

        for target in self.targets:
            if ":" in target:
                user_and_domain, host_parent_dir = target.split(":", 1)
            else:
                user_and_domain, host_parent_dir = "titan@localhost", target
            if "@" in user_and_domain:
                user, domain = user_and_domain.split("@", 1)
            else:
                user = None
                domain = user_and_domain

            relative_src_path = str(src_path).replace(self.host_directory, "")
            target_path = str(Path(host_parent_dir) / relative_src_path)
            self.logger.info("SSH mkdir %s -> %s:%s", src_path, domain, target_path)

            ssh_client = self._get_ssh_client(domain)
            command = f"mkdir -p {target_path}"
            if user:
                ssh_client.exec_command(f'sudo su {user} bash -c "{command}"')
            ssh_client.exec_command(command)

    def _create_parent_dir_if_necessary(self, domain: str, base: Path, relative: Path):
        target_path = base / relative
        if str(target_path) in self._dirs_exists_on_targets[domain]:
            return

        self.ssh_mkdir(str(relative))

        while str(relative).replace(".", "").replace("/", ""):
            target_path = base / relative
            self._dirs_exists_on_targets[domain].add(str(target_path))
            relative = relative.parent

    def _scp_file(self, event: FileModifiedEvent | FileCreatedEvent | FileMovedEvent):
        assert not event.is_directory
        for target in self.targets:
            if ":" in target:
                user_and_domain, host_parent_dir = target.split(":", 1)
            else:
                user_and_domain, host_parent_dir = "titan@localhost", target
            if "@" in user_and_domain:
                user, domain = user_and_domain.split("@", 1)
            else:
                user = None
                domain = user_and_domain

            relative_src_path = str(event.src_path).replace(self.host_directory, "")
            target_path = str(Path(host_parent_dir) / relative_src_path)
            self.logger.info(
                "SCP (as %s) %s -> %s:%s",
                (user or "self"),
                event.src_path,
                domain,
                target_path,
            )

            scp_client = self._get_scp_client(domain)

            # TODO: handle user
            self._create_parent_dir_if_necessary(
                domain, Path(host_parent_dir), Path(relative_src_path).parent
            )
            if user:
                self._get_ssh_client(domain).exec_command(
                    f'sudo su {user} bash -c "chmod g+w {target_path}"'
                )
            scp_client.put(event.src_path, target_path)

            if target_path.endswith(".sh"):
                self.logger.info("SSH chmod +x %s:%s", domain, target_path)
                self._get_ssh_client(domain).exec_command(f"chmod +x {target_path}")

    def _get_ssh_client(self, domain: str) -> SSHClient:
        if domain in self._ssh_clients:
            return self._ssh_clients[domain]

        self._ssh_clients[domain] = ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        ssh.load_system_host_keys()

        ssh_config_path = str(Path.home() / ".ssh/config")
        user_config = SSHConfig().from_path(ssh_config_path).lookup(domain)

        ssh.connect(
            hostname=domain,
            port=user_config.get("port", 22),
            username=user_config.get("user"),
            # password=user_config.get(),
            # pkey=None,
            key_filename=user_config.get("identityfile", [None])[0],
            # timeout=None,
            # allow_agent=True,
            # look_for_keys=True,
            compress=user_config.get("compression", "no") == "yes",
            # sock=None,
            # gss_auth=False,
            # gss_kex=False,
            # gss_deleg_creds=True,
            # gss_host=None,
            # banner_timeout=None,
            # auth_timeout=None,
            # channel_timeout=None,
            # gss_trust_dns=True,
            # passphrase=None,
            # disabled_algorithms=None,
            # transport_factory=None,
            # auth_strategy=None,
        )

        return ssh

    def _get_scp_client(self, domain: str) -> SCPClient:
        if domain in self._scp_clients:
            return self._scp_clients[domain]

        ssh = self._get_ssh_client(domain)

        transport = ssh.get_transport()
        assert transport is not None
        self._scp_clients[domain] = SCPClient(transport)

        return self._scp_clients[domain]

    def close(self):
        """Close all ssh connections."""
        for scp_client in self._scp_clients.values():
            scp_client.close()
