from pathlib import Path


def read_file(file_path: str) -> str:
    try:
        path = Path(file_path)

        # Only allow files inside the data folder
        data_dir = Path("data").resolve()
        target_path = path.resolve()

        if data_dir not in target_path.parents:
            return "Error: Reading outside the data folder is not allowed."

        if not target_path.exists():
            return "Error: File does not exist."

        if not target_path.is_file():
            return "Error: Path is not a file."

        if target_path.suffix.lower() not in [".txt", ".md", ".csv"]:
            return "Error: File type not supported yet."

        content = target_path.read_text(
            encoding="utf-8"
        )

        return content

    except Exception as e:
        return f"File reading error: {str(e)}"