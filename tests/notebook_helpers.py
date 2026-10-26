import ast
import json
from pathlib import Path

def definitions(filename, namespace=None):
    """Load actual notebook functions without training, downloads or UI side effects."""
    notebook = json.loads((Path(__file__).resolve().parents[1] / filename).read_text(encoding="utf-8"))
    nodes = []
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if any(line.lstrip().startswith(("!", "%", "pip ")) for line in source.splitlines()):
            continue
        tree = ast.parse(source)
        nodes.extend(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    scope = {} if namespace is None else namespace
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), scope)
    return scope
