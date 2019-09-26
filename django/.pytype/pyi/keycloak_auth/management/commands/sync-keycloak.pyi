# (generated with --quick)

from typing import Any

BaseCommand: Any
CommandError: Any
clients: module
collections: module
django: module
keycloak: module

class Command(Any):
    help: str
    requires_migrations_checks: bool
    def handle(self, *args, **options) -> None: ...
