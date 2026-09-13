import ast
import operator


# Allowed mathematical operations
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def calculate_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numbers are allowed")

    if isinstance(node, ast.UnaryOp):
        op = OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("Operation not allowed")
        return op(calculate_node(node.operand))

    if isinstance(node, ast.BinOp):
        op = OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("Operation not allowed")

        left = calculate_node(node.left)
        right = calculate_node(node.right)

        return op(left, right)

    raise ValueError("Invalid mathematical expression")


def calculator(expression: str) -> str:
    """
    Safe calculator tool.
    Example:
        calculator("125 * 48")
    """

    try:
        tree = ast.parse(expression, mode="eval")
        result = calculate_node(tree.body)
        return str(result)

    except Exception as e:
        return f"Calculation error: {str(e)}"