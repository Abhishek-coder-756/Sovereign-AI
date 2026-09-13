from pathlib import Path


def write_file(file_path: str, content: str) -> str:
    try:
        path = Path(file_path)

        # Only allow files inside the data folder
        data_dir = Path("data").resolve()
        target_path = path.resolve()

        if data_dir not in target_path.parents:
            return "Error: Writing outside the data folder is not allowed."

        if target_path.suffix.lower() not in [".txt", ".md", ".csv"]:
            return "Error: File type not supported yet."

        target_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        target_path.write_text(
            content,
            encoding="utf-8"
        )

        return f"File successfully written: {file_path}"

    except Exception as e:
        return f"File writing error: {str(e)}"