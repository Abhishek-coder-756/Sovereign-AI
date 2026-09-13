from pathlib import Path


def read_file(file_path: str) -> str:
    try:
        path = Path(file_path).resolve()

        # Project root
        project_root = Path(__file__).resolve().parents[3]

        # Allow files only inside the project's storage or data folders
        allowed_dirs = [
            (project_root / "storage").resolve(),
            (project_root / "data").resolve(),
        ]

        # Security check
        if not any(
            path == allowed_dir or allowed_dir in path.parents
            for allowed_dir in allowed_dirs
        ):
            return "Error: Reading outside the allowed project folders is not allowed."

        if not path.exists():
            return "Error: File does not exist."

        if not path.is_file():
            return "Error: Path is not a file."

        supported_extensions = [
            ".txt",
            ".md",
            ".csv",
            ".pdf",
        ]

        if path.suffix.lower() not in supported_extensions:
            return "Error: File type not supported yet."

        # PDF
        if path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(path))

                text_parts = []

                for page in reader.pages:
                    text = page.extract_text() or ""
                    text_parts.append(text)

                return "\n\n".join(text_parts).strip()

            except ImportError:
                return "Error: pypdf is not installed."

        # Normal text files
        return path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except Exception as e:
        return f"File reading error: {str(e)}"