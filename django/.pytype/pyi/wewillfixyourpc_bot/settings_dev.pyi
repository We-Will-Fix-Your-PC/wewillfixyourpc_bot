
from typing import Any
def __getattr__(name: Any) -> Any: ...
# Caught error in pytype: Bad call
#json.load(_0: TextIO, _1, _2, _3, _4, _5, _6) -> Any: ...
#against:
#def json.load(fp: json._Reader, cls: Optional[Type[json.decoder.JSONDecoder]] = ..., object_hook: Optional[Callable[[dict], Any]] = ..., parse_float: Optional[Callable[[str], Any]] = ..., parse_int: Optional[Callable[[str], Any]] = ..., parse_constant: Optional[Callable[[str], Any]] = ..., object_pairs_hook: Optional[Callable[[List[Tuple[Any, Any]]], Any]] = ..., **kwds) -> Any: ...
# Traceback (most recent call last):
#   File "/usr/local/lib/python3.7/dist-packages/pytype/io.py", line 131, in check_or_generate_pyi
#     input_filename=options.input, options=options, loader=loader)
#   File "/usr/local/lib/python3.7/dist-packages/pytype/io.py", line 89, in generate_pyi
#     analyze.infer_types, input_filename, options, loader)
#   File "/usr/local/lib/python3.7/dist-packages/pytype/io.py", line 62, in _call
#     deep=deep)
#   File "/usr/local/lib/python3.7/dist-packages/pytype/analyze.py", line 693, in infer_types
#     ast = convert_structural.convert_pytd(ast, builtins_pytd, protocols_pytd)
#   File "/usr/local/lib/python3.7/dist-packages/pytype/convert_structural.py", line 279, in convert_pytd
#     mapping, result = solve(ast, builtins_pytd, protocols_pytd)
#   File "/usr/local/lib/python3.7/dist-packages/pytype/convert_structural.py", line 211, in solve
#     ast, builtins_pytd, protocols_pytd).solve(), extract_local(ast)
#   File "/usr/local/lib/python3.7/dist-packages/pytype/convert_structural.py", line 168, in solve
#     factory_partial, solver_partial, partial, complete)
#   File "/usr/local/lib/python3.7/dist-packages/pytype/convert_structural.py", line 108, in match_call_record
#     faulty_signature, pytd_utils.Print(complete)))
# pytype.convert_structural.FlawedQuery: Bad call
# json.load(_0: TextIO, _1, _2, _3, _4, _5, _6) -> Any: ...
# against:
# def json.load(fp: json._Reader, cls: Optional[Type[json.decoder.JSONDecoder]] = ..., object_hook: Optional[Callable[[dict], Any]] = ..., parse_float: Optional[Callable[[str], Any]] = ..., parse_int: Optional[Callable[[str], Any]] = ..., parse_constant: Optional[Callable[[str], Any]] = ..., object_pairs_hook: Optional[Callable[[List[Tuple[Any, Any]]], Any]] = ..., **kwds) -> Any: ...