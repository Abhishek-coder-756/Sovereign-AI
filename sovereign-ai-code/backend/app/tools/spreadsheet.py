from pathlib import Path


def read_spreadsheet(file_path: str) -> str:

    try:
        path = Path(file_path)

        # =====================================================
        # SECURITY: ONLY ALLOW FILES INSIDE DATA OR STORAGE
        # =====================================================

        data_dir = Path("data").resolve()
        storage_dir = Path("storage").resolve()
        target_path = path.resolve()

        if data_dir not in target_path.parents and storage_dir not in target_path.parents and target_path != data_dir and target_path != storage_dir:
            return (
                "Error: Reading outside the data or storage folder "
                "is not allowed."
            )

        # =====================================================
        # CHECK FILE EXISTS
        # =====================================================

        if not target_path.exists():
            return "Error: File does not exist."

        if not target_path.is_file():
            return "Error: Path is not a file."

        # =====================================================
        # CHECK FILE TYPE
        # =====================================================

        suffix = target_path.suffix.lower()
        if suffix not in [".csv", ".xlsx", ".xls"]:
            return "Error: File type not supported."

        # Try pandas first if installed
        try:
            import pandas as pd
            if suffix == ".csv":
                df = pd.read_csv(target_path)
            else:
                df = pd.read_excel(target_path)
            df_preview = df.head(30)
            return df_preview.to_string(index=False)
        except Exception:
            # Fallback to document loader for reliable zero-dependency parsing
            from ai.rag.document_loader import load_document
            docs = load_document(target_path)
            if docs:
                return "\n\n".join(d["text"] for d in docs[:5])
            raise

    except Exception as e:
        return f"Spreadsheet reading error: {str(e)}"