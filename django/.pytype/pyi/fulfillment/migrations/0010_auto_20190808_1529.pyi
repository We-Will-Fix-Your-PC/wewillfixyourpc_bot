# (generated with --quick)

from typing import Any, Iterable, List, Tuple

django: module
migrations: module
models: module

class Migration(Any):
    dependencies: List[Tuple[str, str]]
    operations: list

def create_brands(apps, schema_editor) -> None: ...
def create_ipad_models(apps, schema_editor) -> None: ...
def create_iphone_models(apps, schema_editor) -> None: ...
def create_models(apps, objects: Iterable, brand) -> None: ...
