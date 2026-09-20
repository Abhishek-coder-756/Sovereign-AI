import ast
import subprocess
import sys
import tempfile
from pathlib import Path


# =========================================================
# ALLOWED IMPORTS
# =========================================================

ALLOWED_IMPORTS = {
    "math",
    "statistics",
}


# =========================================================
# BLOCKED BUILT-IN FUNCTIONS
# =========================================================

BLOCKED_BUILTINS = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
}


# =========================================================
# VALIDATE CODE
# =========================================================

def validate_code(code: str):

    tree = ast.parse(
        code,
        mode="exec"
    )

    for node in ast.walk(tree):

        # -----------------------------------------
        # Block dangerous imports
        # -----------------------------------------

        if isinstance(node, ast.Import):

            for alias in node.names:

                if alias.name not in ALLOWED_IMPORTS:

                    raise ValueError(
                        f"Import not allowed: {alias.name}"
                    )


        # -----------------------------------------
        # Block dangerous from-imports
        # -----------------------------------------

        if isinstance(node, ast.ImportFrom):

            if node.module not in ALLOWED_IMPORTS:

                raise ValueError(
                    f"Import not allowed: {node.module}"
                )


        # -----------------------------------------
        # Block dangerous built-in functions
        # -----------------------------------------

        if isinstance(node, ast.Call):

            if isinstance(node.func, ast.Name):

                if node.func.id in BLOCKED_BUILTINS:

                    raise ValueError(
                        f"Function not allowed: {node.func.id}"
                    )


        # -----------------------------------------
        # Block private/system attributes
        # -----------------------------------------

        if isinstance(node, ast.Attribute):

            if node.attr.startswith("__"):

                raise ValueError(
                    f"Private attribute not allowed: {node.attr}"
                )


# =========================================================
# RUN PYTHON CODE
# =========================================================

def run_python_code(code: str):

    temp_path = None

    try:

        # -----------------------------------------
        # Validate code before execution
        # -----------------------------------------

        validate_code(code)


        # -----------------------------------------
        # Create temporary Python file
        # -----------------------------------------

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False
        ) as temp_file:

            temp_file.write(code)

            temp_path = temp_file.name


        # -----------------------------------------
        # Execute code
        # -----------------------------------------

        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=5
        )


        # -----------------------------------------
        # Handle execution error
        # -----------------------------------------

        if result.returncode != 0:

            return (
                f"Code execution error:\n"
                f"{result.stderr}"
            )


        # -----------------------------------------
        # Return output
        # -----------------------------------------

        return result.stdout.strip()


    except SyntaxError as e:

        return (
            f"Syntax error: {str(e)}"
        )


    except ValueError as e:

        return (
            f"Security error: {str(e)}"
        )


    except subprocess.TimeoutExpired:

        return (
            "Error: Code execution timed out."
        )


    except Exception as e:

        return (
            f"Sandbox error: {str(e)}"
        )


    finally:

        # -----------------------------------------
        # Delete temporary file
        # -----------------------------------------

        if temp_path:

            Path(temp_path).unlink(
                missing_ok=True
            )