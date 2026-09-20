from pathlib import Path
import re
import pandas as pd


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_SPREADSHEET_EXTENSIONS = (
    ".csv",
    ".xlsx",
    ".xls",
)


# ============================================================
# SHEET CONFIGURATION
# ============================================================

IGNORED_SHEET_KEYWORDS = (
    "export summary",
    "pivot",
    "table 1 - table 1 pivot",
    "table 2 - table 1 pivot",
    "table 3 - table 1 pivot",
    "table 4 - table 1 pivot",
    "table 5 - table 1 pivot",
    "table 6 - table 1 pivot",
    "table 7 - table 1 pivot",
    "table 8 - table 1 pivot",
    "table 9 - table 1 pivot",
)


# ============================================================
# KNOWN HEADER WORDS
# ============================================================

# These are useful for detecting a real dataset header.
# This also makes the reader work with your Student Spending
# dataset.

COMMON_HEADER_WORDS = {
    "age",
    "gender",
    "subject",
    "year",
    "income",
    "financial",
    "aid",
    "tuition",
    "housing",
    "food",
    "transportation",
    "books",
    "supplies",
    "entertainment",
    "technology",
    "health",
    "wellness",
    "miscellaneous",
    "payment",
    "spending",
    "total",
    "sales",
    "radio",
    "newspaper",
    "tv",
}


# ============================================================
# CHECK IF SHEET IS LIKELY DATA SHEET
# ============================================================

def _is_likely_data_sheet(sheet_name):
    """
    Return False for obvious summary/pivot/export worksheets.
    """

    name = str(sheet_name).strip().lower()

    for keyword in IGNORED_SHEET_KEYWORDS:

        if keyword in name:
            return False

    return True


# ============================================================
# HEADER DETECTION
# ============================================================

def _header_score(row):
    """
    Calculate how likely a row is to be the real header row.

    Example:

    Age | Gender | Year in School | Subject | Monthly Income

    receives a high score.
    """

    if row is None:
        return -1

    values = []

    for value in row:

        if pd.isna(value):
            continue

        text = str(value).strip().lower()

        if text:
            values.append(text)

    if not values:
        return -1

    score = 0

    # Number of non-empty cells.
    if len(values) >= 2:
        score += 5

    if len(values) >= 5:
        score += 5

    if len(values) >= 10:
        score += 5

    # Known dataset words.
    for value in values:

        normalized = re.sub(
            r"[^a-z0-9 ]+",
            " ",
            value
        ).strip()

        words = set(
            normalized.split()
        )

        if words.intersection(
            COMMON_HEADER_WORDS
        ):

            score += 3

    # Penalize numeric-looking headers.
    numeric_count = 0

    for value in values:

        try:

            float(value)
            numeric_count += 1

        except (ValueError, TypeError):
            pass

    if numeric_count == 0:
        score += 5

    return score


# ============================================================
# CLEAN COLUMN NAMES
# ============================================================

def _clean_column_names(df):
    """
    Clean column names after loading.

    Removes completely empty column names and normalizes
    accidental whitespace.
    """

    cleaned_columns = []

    for col in df.columns:

        if pd.isna(col):

            cleaned_columns.append("")

        else:

            cleaned_columns.append(
                str(col).strip()
            )

    df.columns = cleaned_columns

    # --------------------------------------------------------
    # Remove unnamed / completely empty columns.
    # --------------------------------------------------------

    columns_to_keep = []

    for col in df.columns:

        col_text = str(col).strip()

        if not col_text:
            continue

        if col_text.lower().startswith(
            "unnamed:"
        ):
            continue

        columns_to_keep.append(col)

    if columns_to_keep:

        df = df[
            columns_to_keep
        ]

    return df


# ============================================================
# READ EXCEL SHEET
# ============================================================

def _read_excel_sheet(
    excel_file,
    sheet_name
):
    """
    Read one Excel worksheet.

    First read with header=None so we can inspect the worksheet
    and find the real header row.
    """

    raw_df = pd.read_excel(
        excel_file,
        sheet_name=sheet_name,
        header=None
    )

    if raw_df.empty:
        return None

    # --------------------------------------------------------
    # Find the most likely header row.
    # --------------------------------------------------------

    best_row = 0
    best_score = -1

    # Usually the header is near the beginning.
    max_rows_to_check = min(
        15,
        len(raw_df)
    )

    for row_index in range(
        max_rows_to_check
    ):

        row = raw_df.iloc[
            row_index
        ]

        score = _header_score(
            row
        )

        if score > best_score:

            best_score = score
            best_row = row_index

    # --------------------------------------------------------
    # Create dataframe using detected header.
    # --------------------------------------------------------

    headers = raw_df.iloc[
        best_row
    ].tolist()

    df = raw_df.iloc[
        best_row + 1:
    ].copy()

    # Set headers.
    df.columns = headers

    # --------------------------------------------------------
    # Clean empty rows and columns.
    # --------------------------------------------------------

    df = df.dropna(
        axis=0,
        how="all"
    )

    df = df.dropna(
        axis=1,
        how="all"
    )

    df = _clean_column_names(
        df
    )

    # --------------------------------------------------------
    # Reset index.
    # --------------------------------------------------------

    df = df.reset_index(
        drop=True
    )

    return df


# ============================================================
# SHEET SCORE
# ============================================================

def _sheet_score(
    df,
    sheet_name
):
    """
    Score worksheet according to likelihood of being the
    actual dataset.
    """

    if df is None or df.empty:
        return -1000

    score = 0

    rows = len(df)
    columns = len(df.columns)

    # --------------------------------------------------------
    # Basic dimensions.
    # --------------------------------------------------------

    if rows >= 10:
        score += 10

    if rows >= 100:
        score += 10

    if columns >= 2:
        score += 5

    if columns >= 5:
        score += 5

    if columns >= 10:
        score += 5

    # --------------------------------------------------------
    # Sheet name.
    # --------------------------------------------------------

    if not _is_likely_data_sheet(
        sheet_name
    ):

        score -= 100

    if (
        str(sheet_name)
        .strip()
        .lower()
        == "sheet1"
    ):

        score += 50

    # --------------------------------------------------------
    # Column quality.
    # --------------------------------------------------------

    valid_columns = 0

    for col in df.columns:

        text = str(
            col
        ).strip()

        if (
            text
            and not text.lower().startswith(
                "unnamed"
            )
        ):

            valid_columns += 1

    score += valid_columns

    # --------------------------------------------------------
    # Known dataset columns.
    # --------------------------------------------------------

    for col in df.columns:

        col_text = str(
            col
        ).strip().lower()

        normalized = re.sub(
            r"[^a-z0-9 ]+",
            " ",
            col_text
        )

        words = set(
            normalized.split()
        )

        if words.intersection(
            COMMON_HEADER_WORDS
        ):

            score += 4

    return score


# ============================================================
# LOAD SPREADSHEET
# ============================================================

def _load_dataframe(file_path):
    """
    Load CSV/XLS/XLSX into a Pandas DataFrame.

    CSV:
        Directly loaded.

    XLS/XLSX:
        All worksheets are inspected.

        Summary/pivot/export sheets are avoided.

        The most likely real data sheet is selected.
    """

    path = Path(
        file_path
    )

    if not path.exists():

        raise FileNotFoundError(
            f"Spreadsheet file not found: {file_path}"
        )

    if not path.is_file():

        raise ValueError(
            f"Path is not a file: {file_path}"
        )

    suffix = path.suffix.lower()

    # ========================================================
    # CSV
    # ========================================================

    if suffix == ".csv":

        df = pd.read_csv(
            path
        )

        if df.empty:

            raise ValueError(
                "CSV file is empty."
            )

        df = _clean_column_names(
            df
        )

        return df

    # ========================================================
    # EXCEL
    # ========================================================

    if suffix in (
        ".xlsx",
        ".xls"
    ):

        excel_file = pd.ExcelFile(
            path
        )

        sheet_names = (
            excel_file.sheet_names
        )

        if not sheet_names:

            raise ValueError(
                "Excel workbook does not contain worksheets."
            )

        candidates = []

        # ----------------------------------------------------
        # Inspect every worksheet.
        # ----------------------------------------------------

        for sheet_name in sheet_names:

            try:

                df = _read_excel_sheet(
                    excel_file,
                    sheet_name
                )

                if df is None:
                    continue

                if df.empty:
                    continue

                score = _sheet_score(
                    df,
                    sheet_name
                )

                candidates.append(
                    (
                        score,
                        sheet_name,
                        df
                    )
                )

            except Exception:
                continue

        if not candidates:

            raise ValueError(
                "No usable data worksheet was found."
            )

        # ----------------------------------------------------
        # Highest score = most likely actual dataset.
        # ----------------------------------------------------

        candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )

        (
            best_score,
            best_sheet,
            best_df
        ) = candidates[0]

        # ----------------------------------------------------
        # Remove completely empty rows/columns.
        # ----------------------------------------------------

        best_df = best_df.dropna(
            axis=0,
            how="all"
        )

        best_df = best_df.dropna(
            axis=1,
            how="all"
        )

        best_df = best_df.reset_index(
            drop=True
        )

        # ----------------------------------------------------
        # Store metadata.
        # ----------------------------------------------------

        best_df.attrs[
            "sheet_name"
        ] = best_sheet

        best_df.attrs[
            "sheet_names"
        ] = sheet_names

        best_df.attrs[
            "sheet_score"
        ] = best_score

        return best_df

    # ========================================================
    # UNSUPPORTED
    # ========================================================

    raise ValueError(
        f"Unsupported spreadsheet format: {suffix}"
    )


# ============================================================
# FIND COLUMN
# ============================================================

def _find_column(
    df,
    column
):
    """
    Find a dataframe column safely.

    Matching:
        1. exact
        2. normalized
        3. partial
    """

    if column is None:

        raise ValueError(
            "No column was specified."
        )

    requested = str(
        column
    ).strip().lower()

    # --------------------------------------------------------
    # Exact match.
    # --------------------------------------------------------

    for col in df.columns:

        if (
            str(col)
            .strip()
            .lower()
            == requested
        ):

            return col

    # --------------------------------------------------------
    # Normalized match.
    # --------------------------------------------------------

    normalized_requested = re.sub(
        r"[^a-z0-9]+",
        "",
        requested
    )

    for col in df.columns:

        normalized_column = re.sub(
            r"[^a-z0-9]+",
            "",
            str(col)
            .strip()
            .lower()
        )

        if (
            normalized_column
            == normalized_requested
        ):

            return col

    # --------------------------------------------------------
    # Partial match.
    # --------------------------------------------------------

    for col in df.columns:

        col_text = (
            str(col)
            .strip()
            .lower()
        )

        if requested in col_text:

            return col

    raise ValueError(
        f"Column '{column}' not found. "
        f"Available columns: {list(df.columns)}"
    )


# ============================================================
# FIND COLUMN FROM QUERY
# ============================================================

def _find_mentioned_column(
    df,
    query
):
    """
    Find the dataframe column mentioned in a natural-language
    query.

    Examples:

        average monthly income
        highest total spending
        top 5 tuition
        unique gender
    """

    q = (
        query or ""
    ).lower()

    # --------------------------------------------------------
    # Try longest column names first.
    # --------------------------------------------------------

    columns = sorted(
        df.columns,
        key=lambda col: len(
            str(col)
        ),
        reverse=True
    )

    for col in columns:

        column_text = (
            str(col)
            .strip()
            .lower()
        )

        if not column_text:
            continue

        # Direct phrase.
        if column_text in q:

            return col

        # Normalized phrase.
        normalized_column = re.sub(
            r"[^a-z0-9]+",
            " ",
            column_text
        ).strip()

        if (
            normalized_column
            and normalized_column in q
        ):

            return col

    # --------------------------------------------------------
    # Word-based matching.
    # --------------------------------------------------------

    best_column = None
    best_score = 0

    for col in columns:

        words = re.findall(
            r"[a-z0-9]+",
            str(col).lower()
        )

        useful_words = [
            word
            for word in words
            if len(word) > 2
        ]

        if not useful_words:
            continue

        matched = 0

        for word in useful_words:

            if re.search(
                rf"\b{re.escape(word)}\b",
                q
            ):

                matched += 1

        score = matched / len(
            useful_words
        )

        if (
            matched > 0
            and score > best_score
        ):

            best_score = score
            best_column = col

    return best_column


# ============================================================
# NUMERIC VALUES
# ============================================================

def _numeric_values(
    df,
    column
):
    """
    Convert dataframe column to numeric values.
    """

    column = _find_column(
        df,
        column
    )

    values = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    if values.isna().all():

        raise ValueError(
            f"Column '{column}' does not contain numeric values."
        )

    return column, values


# ============================================================
# READ SPREADSHEET
# ============================================================

def read_spreadsheet(
    file_path
):
    """
    Return a readable preview of the spreadsheet.
    """

    try:

        df = _load_dataframe(
            file_path
        )

        if df.empty:

            return (
                "Spreadsheet is empty."
            )

        output = []

        output.append(
            "=== SPREADSHEET ==="
        )

        output.append("")

        sheet_name = df.attrs.get(
            "sheet_name"
        )

        if sheet_name:

            output.append(
                f"Selected Sheet: {sheet_name}"
            )

        output.append(
            f"Rows: {len(df)}"
        )

        output.append(
            f"Columns: {len(df.columns)}"
        )

        output.append(
            "Column names: "
            + ", ".join(
                map(
                    str,
                    df.columns
                )
            )
        )

        output.append("")

        output.append(
            "=== DATA ==="
        )

        output.append("")

        # Show first 100 rows only.
        preview = df.head(
            100
        )

        output.append(
            preview.to_string(
                index=False
            )
        )

        if len(df) > 100:

            output.append("")

            output.append(
                f"... showing first 100 of "
                f"{len(df)} rows ..."
            )

        return "\n".join(
            output
        )

    except Exception as e:

        return (
            f"Spreadsheet reading error: {str(e)}"
        )


# ============================================================
# MAXIMUM
# ============================================================

def _maximum_result(
    df,
    column
):
    """
    Return maximum value and complete corresponding row.
    """

    column, values = _numeric_values(
        df,
        column
    )

    index = values.idxmax()

    row = df.loc[
        index
    ]

    output = []

    output.append(
        f"=== HIGHEST {str(column).upper()} ==="
    )

    output.append("")

    for col in df.columns:

        output.append(
            f"{col}: {row[col]}"
        )

    return "\n".join(
        output
    )


# ============================================================
# MINIMUM
# ============================================================

def _minimum_result(
    df,
    column
):
    """
    Return minimum value and complete corresponding row.
    """

    column, values = _numeric_values(
        df,
        column
    )

    index = values.idxmin()

    row = df.loc[
        index
    ]

    output = []

    output.append(
        f"=== LOWEST {str(column).upper()} ==="
    )

    output.append("")

    for col in df.columns:

        output.append(
            f"{col}: {row[col]}"
        )

    return "\n".join(
        output
    )


# ============================================================
# AVERAGE
# ============================================================

def _average_result(
    df,
    column
):
    """
    Calculate exact average.
    """

    column, values = _numeric_values(
        df,
        column
    )

    average = values.mean()

    return (
        f"=== AVERAGE {str(column).upper()} ===\n\n"
        f"{average:.6f}"
    )


# ============================================================
# SUM
# ============================================================

def _sum_result(
    df,
    column
):
    """
    Calculate exact total.
    """

    column, values = _numeric_values(
        df,
        column
    )

    total = values.sum()

    return (
        f"=== TOTAL {str(column).upper()} ===\n\n"
        f"{total:.6f}"
    )


# ============================================================
# COUNT
# ============================================================

def _count_result(
    df,
    column=None
):
    """
    Count records or non-empty values.
    """

    if column is None:

        return (
            "=== RECORD COUNT ===\n\n"
            f"{len(df)}"
        )

    column = _find_column(
        df,
        column
    )

    count = df[
        column
    ].count()

    return (
        f"=== COUNT OF {str(column).upper()} ===\n\n"
        f"{count}"
    )


# ============================================================
# TOP N
# ============================================================

def _top_records(
    df,
    column,
    n=5
):
    """
    Return top N records using Pandas.
    """

    column, numeric_values = _numeric_values(
        df,
        column
    )

    n = max(
        1,
        min(
            n,
            len(df)
        )
    )

    result = (
        df.assign(
            __sort_value=numeric_values
        )
        .sort_values(
            by="__sort_value",
            ascending=False
        )
        .head(n)
        .drop(
            columns=[
                "__sort_value"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    result.insert(
        0,
        "Rank",
        range(
            1,
            len(result) + 1
        )
    )

    return (
        f"=== TOP {len(result)} RECORDS BY "
        f"{str(column).upper()} ===\n\n"
        + result.to_markdown(
            index=False
        )
    )


# ============================================================
# BOTTOM N
# ============================================================

def _bottom_records(
    df,
    column,
    n=5
):
    """
    Return bottom N records using Pandas.
    """

    column, numeric_values = _numeric_values(
        df,
        column
    )

    n = max(
        1,
        min(
            n,
            len(df)
        )
    )

    result = (
        df.assign(
            __sort_value=numeric_values
        )
        .sort_values(
            by="__sort_value",
            ascending=True
        )
        .head(n)
        .drop(
            columns=[
                "__sort_value"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    result.insert(
        0,
        "Rank",
        range(
            1,
            len(result) + 1
        )
    )

    return (
        f"=== BOTTOM {len(result)} RECORDS BY "
        f"{str(column).upper()} ===\n\n"
        + result.to_markdown(
            index=False
        )
    )


# ============================================================
# DATASET SIZE
# ============================================================

def _dataset_size(
    df
):

    return (
        "=== DATASET SIZE ===\n\n"
        f"Rows: {len(df)}\n"
        f"Columns: {len(df.columns)}"
    )


# ============================================================
# COLUMN NAMES
# ============================================================

def _column_names(
    df
):

    output = []

    output.append(
        "=== COLUMN NAMES ==="
    )

    output.append("")

    for i, col in enumerate(
        df.columns,
        start=1
    ):

        output.append(
            f"{i}. {col}"
        )

    return "\n".join(
        output
    )


# ============================================================
# MISSING VALUES
# ============================================================

def _missing_values(
    df
):

    missing = df.isnull().sum()

    output = []

    output.append(
        "=== MISSING VALUES ==="
    )

    output.append("")

    for col, count in missing.items():

        output.append(
            f"{col}: {count}"
        )

    return "\n".join(
        output
    )


# ============================================================
# CORRELATION
# ============================================================

def _correlation_result(
    df,
    column1,
    column2
):

    column1, values1 = _numeric_values(
        df,
        column1
    )

    column2, values2 = _numeric_values(
        df,
        column2
    )

    correlation = values1.corr(
        values2
    )

    return (
        "=== CORRELATION ===\n\n"
        f"{column1} vs {column2}: "
        f"{correlation:.6f}"
    )


# ============================================================
# UNIQUE VALUES
# ============================================================

def _unique_result(
    df,
    column
):

    column = _find_column(
        df,
        column
    )

    values = (
        df[column]
        .dropna()
        .unique()
    )

    output = []

    output.append(
        f"=== UNIQUE VALUES OF "
        f"{str(column).upper()} ==="
    )

    output.append("")

    for value in values:

        output.append(
            str(value)
        )

    return "\n".join(
        output
    )


# ============================================================
# DATASET SUMMARY
# ============================================================

def _dataset_summary(
    df
):

    output = []

    output.append(
        "=== DATASET SUMMARY ==="
    )

    output.append("")

    output.append(
        f"Rows: {len(df)}"
    )

    output.append(
        f"Columns: {len(df.columns)}"
    )

    output.append("")

    output.append(
        "=== COLUMN INFORMATION ==="
    )

    output.append("")

    for col in df.columns:

        dtype = str(
            df[col].dtype
        )

        missing = int(
            df[col].isna().sum()
        )

        unique = int(
            df[col].nunique(
                dropna=True
            )
        )

        output.append(
            f"{col} | "
            f"type={dtype} | "
            f"missing={missing} | "
            f"unique={unique}"
        )

    output.append("")

    output.append(
        "=== NUMERIC SUMMARY ==="
    )

    output.append("")

    numeric_df = df.select_dtypes(
        include="number"
    )

    if numeric_df.empty:

        output.append(
            "No numeric columns found."
        )

    else:

        output.append(
            numeric_df.describe().to_string()
        )

    return "\n".join(
        output
    )


# ============================================================
# MAIN SPREADSHEET ANALYZER
# ============================================================

def analyze_spreadsheet(
    file_path,
    query
):
    """
    Main deterministic spreadsheet analysis.

    The LLM is NOT used to calculate values.

    Pandas performs:
        - sorting
        - average
        - sum
        - min
        - max
        - count
        - correlation
        - unique values
    """

    try:

        df = _load_dataframe(
            file_path
        )

        if df.empty:

            return (
                "Spreadsheet is empty."
            )

        q = (
            query or ""
        ).lower().strip()

        # ====================================================
        # DATASET SIZE
        # ====================================================

        if (
            "how many rows" in q
            or "number of rows" in q
            or "dataset size" in q
            or "size of dataset" in q
            or "how many records" in q
            or "number of records" in q
            or "record count" in q
            or "count records" in q
        ):

            return _dataset_size(
                df
            )

        # ====================================================
        # COLUMN NAMES
        # ====================================================

        if (
            "column names" in q
            or "what columns" in q
            or "list columns" in q
            or "columns are there" in q
            or "columns does" in q
        ):

            return _column_names(
                df
            )

        # ====================================================
        # MISSING VALUES
        # ====================================================

        if (
            "missing values" in q
            or "null values" in q
            or "missing data" in q
            or "missing columns" in q
        ):

            return _missing_values(
                df
            )

        # ====================================================
        # TOP N
        # ====================================================

        top_pattern = re.search(
            r"\b(top|highest|best)\s+"
            r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            q
        )

        if top_pattern:

            n = _extract_rank_number(
                q,
                default=5
            )

            column = _find_mentioned_column(
                df,
                q
            )

            if column is not None:

                return _top_records(
                    df,
                    column,
                    n
                )

        # ====================================================
        # BOTTOM N
        # ====================================================

        bottom_pattern = re.search(
            r"\b(bottom|lowest|worst)\s+"
            r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            q
        )

        if bottom_pattern:

            n = _extract_rank_number(
                q,
                default=5
            )

            column = _find_mentioned_column(
                df,
                q
            )

            if column is not None:

                return _bottom_records(
                    df,
                    column,
                    n
                )

        # ====================================================
        # HIGHEST / MAXIMUM
        # ====================================================

        if (
            "highest" in q
            or "maximum" in q
            or "max " in q
            or q.startswith("max")
        ):

            column = _find_mentioned_column(
                df,
                q
            )

            if column is not None:

                return _maximum_result(
                    df,
                    column
                )

        # ====================================================
        # LOWEST / MINIMUM
        # ====================================================

        if (
            "lowest" in q
            or "minimum" in q
            or "min " in q
            or q.startswith("min")
        ):

            column = _find_mentioned_column(
                df,
                q
            )

            if column is not None:

                return _minimum_result(
                    df,
                    column
                )

        # ====================================================
        # AVERAGE / MEAN
        # ====================================================

        if (
            "average" in q
            or "mean" in q
            or "avg" in q
        ):

            column = _find_mentioned_column(
                df,
                q
            )

            if column is not None:

                return _average_result(
                    df,
                    column
                )

        # ====================================================
        # TOTAL / SUM
        # ====================================================

        if (
            "total" in q
            or "sum" in q
        ):

            column = _find_mentioned_column(
                df,
                q
            )

            if column is not None:

                return _sum_result(
                    df,
                    column
                )

        # ====================================================
        # COUNT
        # ====================================================

        if (
            "count" in q
            or "how many" in q
        ):

            column = _find_mentioned_column(
                df,
                q
            )

            if column is not None:

                return _count_result(
                    df,
                    column
                )

        # ====================================================
        # CORRELATION
        # ====================================================

        if (
            "correlation" in q
            or "correlate" in q
            or "relationship between" in q
        ):

            mentioned_columns = []

            # Direct column matching.
            for col in df.columns:

                column_text = (
                    str(col)
                    .strip()
                    .lower()
                )

                if (
                    column_text
                    and column_text in q
                ):

                    mentioned_columns.append(
                        col
                    )

            # Normalized/word matching.
            if len(
                mentioned_columns
            ) < 2:

                for col in df.columns:

                    words = re.findall(
                        r"[a-z0-9]+",
                        str(col).lower()
                    )

                    useful_words = [
                        word
                        for word in words
                        if len(word) > 2
                    ]

                    if not useful_words:
                        continue

                    matched = 0

                    for word in useful_words:

                        if re.search(
                            rf"\b{re.escape(word)}\b",
                            q
                        ):

                            matched += 1

                    if matched == len(
                        useful_words
                    ):

                        if col not in mentioned_columns:

                            mentioned_columns.append(
                                col
                            )

            if len(
                mentioned_columns
            ) >= 2:

                return _correlation_result(
                    df,
                    mentioned_columns[0],
                    mentioned_columns[1]
                )

        # ====================================================
        # UNIQUE / DISTINCT
        # ====================================================

        if (
            "unique" in q
            or "distinct" in q
        ):

            column = _find_mentioned_column(
                df,
                q
            )

            if column is not None:

                return _unique_result(
                    df,
                    column
                )

        # ====================================================
        # GENERAL SUMMARY
        # ====================================================

        if (
            "summary" in q
            or "summarize" in q
            or "statistics" in q
            or "stats" in q
            or "describe dataset" in q
            or "describe the dataset" in q
        ):

            return _dataset_summary(
                df
            )

        # ====================================================
        # FALLBACK
        # ====================================================

        return read_spreadsheet(
            file_path
        )

    except Exception as e:

        return (
            f"Spreadsheet analysis error: {str(e)}"
        )


# ============================================================
# HELPER: RANK NUMBER
# ============================================================

def _extract_rank_number(
    query,
    default=5
):
    """
    Extract number from queries such as:

        top 5
        top five
        highest 10
        bottom 3
        lowest five
    """

    pattern = re.search(
        r"\b("
        r"top|highest|best|bottom|lowest|worst"
        r")\s+"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\b",
        (query or "").lower()
    )

    if not pattern:

        return default

    value = pattern.group(2)

    if value.isdigit():

        return int(value)

    return {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }.get(
        value,
        default
    )