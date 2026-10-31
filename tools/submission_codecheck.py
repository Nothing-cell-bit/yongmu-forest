"""Guard the reported nullable portal-state E1137 pattern, not all code_check rules."""
import ast
from pathlib import Path


def script_issues(data, name):
    source = data.decode("utf-8-sig")
    try:
        tree = ast.parse(source, filename=name)
    except SyntaxError:
        from lib2to3.refactor import RefactoringTool
        reader = RefactoringTool(["lib2to3.fixes.fix_print", "lib2to3.fixes.fix_except",
                                  "lib2to3.fixes.fix_raise"])
        tree = ast.parse(str(reader.refactor_string(source + "\n", name)), filename=name)
    issues = []
    for method in ast.walk(tree):
        if not isinstance(method, ast.FunctionDef):
            continue
        nullable = set()
        for node in ast.walk(method):
            if not isinstance(node, ast.Assign):
                continue
            call = node.value
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "getattr" and len(call.args) == 3
                    and isinstance(call.args[1], ast.Constant)
                    and call.args[1].value == "_portal_background_preload_inflight"
                    and isinstance(call.args[2], ast.Constant) and call.args[2].value is None):
                nullable.update(t.id for t in node.targets if isinstance(t, ast.Name))
        for node in ast.walk(method):
            if (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
                    and isinstance(node.value, ast.Name) and node.value.id in nullable):
                issues.append({"path": name, "line": node.lineno,
                               "symbol": "known-portal-state-E1137",
                               "reason": "Use a dictionary guard and update() for nullable portal state"})
    return issues


def check_rows(rows):
    return [issue for name, data in rows if name.endswith(".py")
            and name.startswith("behavior_pack/") for issue in script_issues(data, name)]


def require_clean(rows):
    issues = check_rows(rows)
    if issues:
        raise ValueError("Known submission code_check pattern: " + repr(issues))


def check_source(behavior_pack):
    root = Path(behavior_pack)
    require_clean(("behavior_pack/" + p.relative_to(root).as_posix(), p.read_bytes())
                  for p in root.rglob("*.py"))
