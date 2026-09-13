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
# LOAD SPREADSHEET
# ============================================================

def _load_dataframe(file_path):
    """
    Load CSV/XLS/XLSX file into a Pandas DataFrame.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Spreadsheet file not found: {file_path}"
        )

    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)

    elif suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)

    else:
        raise ValueError(
            f"Unsupported spreadsheet format: {suffix}"
        )


# ============================================================
# FIND COLUMN
# ============================================================

def _find_column(df, column):
    """
    Find a column safely, ignoring case and extra spaces.
    """

    if column is None:
        raise ValueError("No column was specified.")

    requested = str(column).strip().lower()

    # Exact match
    for col in df.columns:
        if str(col).strip().lower() == requested:
            return col

    # Partial match
    for col in df.columns:
        if requested in str(col).strip().lower():
            return col

    raise ValueError(
        f"Column '{column}' not found. "
        f"Available columns: {list(df.columns)}"
    )


# ============================================================
# COLUMN NAME HELPERS
# ============================================================

def _mentions_sales(q):
    """
    Detect both singular and plural forms of Sales.

    Examples:
        sale
        sales
        SALE
        SALES
    """

    q = (q or "").lower()

    return bool(
        re.search(r"\bsales?\b", q)
    )


def _mentions_tv(q):
    """
    Detect TV column.
    """

    q = (q or "").lower()

    return bool(
        re.search(r"\btv\b", q)
    )


def _mentions_radio(q):
    """
    Detect Radio column.
    """

    q = (q or "").lower()

    return bool(
        re.search(r"\bradio\b", q)
    )


def _mentions_newspaper(q):
    """
    Detect Newspaper column.
    """

    q = (q or "").lower()

    return "newspaper" in q


# ============================================================
# NUMBER DETECTION
# ============================================================

def _extract_number(q, default=5):
    """
    Extract a number from a query.

    Examples:
        top 5       -> 5
        top 10      -> 10
        highest 7   -> 7

    If no number is found, return default.
    """

    match = re.search(r"\b(\d+)\b", q)

    if match:
        try:
            number = int(match.group(1))

            if number > 0:
                return number

        except ValueError:
            pass

    return default


# ============================================================
# READ SPREADSHEET
# ============================================================

def read_spreadsheet(file_path):
    """
    Read spreadsheet and return a basic textual representation.
    """

    try:

        df = _load_dataframe(file_path)

        if df.empty:
            return "Spreadsheet is empty."

        output = []

        output.append("=== SPREADSHEET ===")
        output.append("")

        output.append(
            f"Rows: {len(df)}"
        )

        output.append(
            f"Columns: {len(df.columns)}"
        )

        output.append(
            f"Column names: {', '.join(map(str, df.columns))}"
        )

        output.append("")

        output.append("=== DATA ===")
        output.append("")

        output.append(
            df.to_string(index=False)
        )

        return "\n".join(output)

    except Exception as e:

        return (
            f"Spreadsheet reading error: {str(e)}"
        )


# ============================================================
# MAXIMUM
# ============================================================

def _maximum_result(df, column):
    """
    Return maximum value and corresponding row.
    """

    column = _find_column(df, column)

    numeric_values = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    if numeric_values.isna().all():
        raise ValueError(
            f"Column '{column}' does not contain numeric values."
        )

    index = numeric_values.idxmax()

    row = df.loc[index]

    output = []

    output.append(
        f"=== HIGHEST {str(column).upper()} ==="
    )

    output.append("")

    for col in df.columns:

        output.append(
            f"{col}: {row[col]}"
        )

    return "\n".join(output)


# ============================================================
# MINIMUM
# ============================================================

def _minimum_result(df, column):
    """
    Return minimum value and corresponding row.
    """

    column = _find_column(df, column)

    numeric_values = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    if numeric_values.isna().all():
        raise ValueError(
            f"Column '{column}' does not contain numeric values."
        )

    index = numeric_values.idxmin()

    row = df.loc[index]

    output = []

    output.append(
        f"=== LOWEST {str(column).upper()} ==="
    )

    output.append("")

    for col in df.columns:

        output.append(
            f"{col}: {row[col]}"
        )

    return "\n".join(output)


# ============================================================
# AVERAGE
# ============================================================

def _average_result(df, column):
    """
    Calculate average of a numeric column.
    """

    column = _find_column(df, column)

    values = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    if values.isna().all():
        raise ValueError(
            f"Column '{column}' does not contain numeric values."
        )

    average = values.mean()

    return (
        f"=== AVERAGE {str(column).upper()} ===\n\n"
        f"{average}"
    )


# ============================================================
# SUM
# ============================================================

def _sum_result(df, column):
    """
    Calculate sum of a numeric column.
    """

    column = _find_column(df, column)

    values = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    if values.isna().all():
        raise ValueError(
            f"Column '{column}' does not contain numeric values."
        )

    total = values.sum()

    return (
        f"=== TOTAL {str(column).upper()} ===\n\n"
        f"{total}"
    )


# ============================================================
# COUNT
# ============================================================

def _count_result(df, column=None):
    """
    Count records or non-empty values.
    """

    if column is None:

        count = len(df)

        return (
            "=== RECORD COUNT ===\n\n"
            f"{count}"
        )

    column = _find_column(df, column)

    count = df[column].count()

    return (
        f"=== COUNT OF {str(column).upper()} ===\n\n"
        f"{count}"
    )


# ============================================================
# TOP N RECORDS
# ============================================================

def _top_records(df, column, n=5):
    """
    Return top N records in a clean column-wise table.

    Sorting/calculation is performed by Pandas.
    The LLM is NOT used to calculate or select records.
    """

    column = _find_column(df, column)

    numeric_values = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    if numeric_values.isna().all():

        raise ValueError(
            f"Column '{column}' does not contain numeric values."
        )

    # --------------------------------------------------------
    # Sort using Pandas
    # --------------------------------------------------------

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
            columns=["__sort_value"]
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # Add Rank column
    # --------------------------------------------------------

    result.insert(
        0,
        "Rank",
        range(
            1,
            len(result) + 1
        )
    )

    # --------------------------------------------------------
    # Convert to Markdown table
    # --------------------------------------------------------

    return (
        f"=== TOP {len(result)} RECORDS BY "
        f"{str(column).upper()} ===\n\n"
        + result.to_markdown(
            index=False
        )
    )


# ============================================================
# BOTTOM N RECORDS
# ============================================================

def _bottom_records(df, column, n=5):
    """
    Return bottom N records in a clean column-wise table.
    """

    column = _find_column(df, column)

    numeric_values = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    if numeric_values.isna().all():

        raise ValueError(
            f"Column '{column}' does not contain numeric values."
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
            columns=["__sort_value"]
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

def _dataset_size(df):
    """
    Return number of rows and columns.
    """

    return (
        "=== DATASET SIZE ===\n\n"
        f"Rows: {len(df)}\n"
        f"Columns: {len(df.columns)}"
    )


# ============================================================
# COLUMN NAMES
# ============================================================

def _column_names(df):
    """
    Return all column names.
    """

    output = []

    output.append("=== COLUMN NAMES ===")
    output.append("")

    for i, col in enumerate(
        df.columns,
        start=1
    ):

        output.append(
            f"{i}. {col}"
        )

    return "\n".join(output)


# ============================================================
# MISSING VALUES
# ============================================================

def _missing_values(df):
    """
    Return missing-value count for every column.
    """

    missing = df.isnull().sum()

    output = []

    output.append("=== MISSING VALUES ===")
    output.append("")

    for col, count in missing.items():

        output.append(
            f"{col}: {count}"
        )

    return "\n".join(output)


# ============================================================
# CORRELATION
# ============================================================

def _correlation_result(
    df,
    column1,
    column2
):
    """
    Calculate correlation between two numeric columns.
    """

    column1 = _find_column(
        df,
        column1
    )

    column2 = _find_column(
        df,
        column2
    )

    values1 = pd.to_numeric(
        df[column1],
        errors="coerce"
    )

    values2 = pd.to_numeric(
        df[column2],
        errors="coerce"
    )

    correlation = values1.corr(
        values2
    )

    return (
        "=== CORRELATION ===\n\n"
        f"{column1} vs {column2}: "
        f"{correlation}"
    )


# ============================================================
# UNIQUE VALUES
# ============================================================

def _unique_result(df, column):
    """
    Return unique values of a column.
    """

    column = _find_column(
        df,
        column
    )

    values = df[column].dropna().unique()

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

    return "\n".join(output)


# ============================================================
# DATASET SUMMARY
# ============================================================

def _dataset_summary(df):
    """
    Return a general numerical summary.
    """

    output = []

    output.append("=== DATASET SUMMARY ===")
    output.append("")

    output.append(
        f"Rows: {len(df)}"
    )

    output.append(
        f"Columns: {len(df.columns)}"
    )

    output.append("")

    output.append(
        df.describe(
            include="all"
        ).to_string()
    )

    return "\n".join(output)


# ============================================================
# MAIN SPREADSHEET ANALYZER
# ============================================================

def analyze_spreadsheet(
    file_path,
    query
):
    """
    Main deterministic spreadsheet analysis function.

    CSV/XLS/XLSX → Pandas → exact calculation → result.

    The LLM is not used for calculations.
    """

    try:

        df = _load_dataframe(
            file_path
        )

        if df.empty:
            return "Spreadsheet is empty."

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
        ):

            return _dataset_size(df)

        # ====================================================
        # COLUMN NAMES
        # ====================================================

        if (
            "column names" in q
            or "what columns" in q
            or "list columns" in q
            or "columns are there" in q
        ):

            return _column_names(df)

        # ====================================================
        # MISSING VALUES
        # ====================================================

        if (
            "missing values" in q
            or "null values" in q
            or "missing data" in q
        ):

            return _missing_values(df)

        # ====================================================
        # TOP N
        # ====================================================

        # Supports:
        #
        # top 5
        # top 10
        # highest 5
        # highest 10
        # best 5
        # best 10
        # top five
        # highest five
        # best five

        top_pattern = re.search(
            r"\b(top|highest|best)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            q
        )

        word_numbers = {
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
        }

        if top_pattern:

            number_text = top_pattern.group(2)

            if number_text.isdigit():

                n = int(number_text)

            else:

                n = word_numbers.get(
                    number_text,
                    5
                )

            # Safety limit
            n = max(
                1,
                min(n, len(df))
            )

            # ------------------------------------------------
            # SALES
            # ------------------------------------------------

            if _mentions_sales(q):

                return _top_records(
                    df,
                    "Sales",
                    n
                )

            # ------------------------------------------------
            # TV
            # ------------------------------------------------

            if _mentions_tv(q):

                return _top_records(
                    df,
                    "TV",
                    n
                )

            # ------------------------------------------------
            # RADIO
            # ------------------------------------------------

            if _mentions_radio(q):

                return _top_records(
                    df,
                    "Radio",
                    n
                )

            # ------------------------------------------------
            # NEWSPAPER
            # ------------------------------------------------

            if _mentions_newspaper(q):

                return _top_records(
                    df,
                    "Newspaper",
                    n
                )

        # ====================================================
        # BOTTOM N
        # ====================================================

        bottom_pattern = re.search(
            r"\b(bottom|lowest|worst)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            q
        )

        if bottom_pattern:

            number_text = bottom_pattern.group(2)

            if number_text.isdigit():

                n = int(number_text)

            else:

                n = word_numbers.get(
                    number_text,
                    5
                )

            n = max(
                1,
                min(n, len(df))
            )

            # SALES
            if _mentions_sales(q):

                return _bottom_records(
                    df,
                    "Sales",
                    n
                )

            # TV
            if _mentions_tv(q):

                return _bottom_records(
                    df,
                    "TV",
                    n
                )

            # RADIO
            if _mentions_radio(q):

                return _bottom_records(
                    df,
                    "Radio",
                    n
                )

            # NEWSPAPER
            if _mentions_newspaper(q):

                return _bottom_records(
                    df,
                    "Newspaper",
                    n
                )

        # ====================================================
        # HIGHEST SALES
        # ====================================================

        if (
            "highest sales" in q
            or "maximum sales" in q
            or "max sales" in q
            or "highest sale" in q
            or "maximum sale" in q
            or "max sale" in q
        ):

            return _maximum_result(
                df,
                "Sales"
            )

        # ====================================================
        # LOWEST SALES
        # ====================================================

        if (
            "lowest sales" in q
            or "minimum sales" in q
            or "min sales" in q
            or "lowest sale" in q
            or "minimum sale" in q
            or "min sale" in q
        ):

            return _minimum_result(
                df,
                "Sales"
            )

        # ====================================================
        # AVERAGE SALES
        # ====================================================

        if (
            "average sales" in q
            or "mean sales" in q
            or "avg sales" in q
            or "average sale" in q
            or "mean sale" in q
            or "avg sale" in q
        ):

            return _average_result(
                df,
                "Sales"
            )

        # ====================================================
        # TOTAL SALES
        # ====================================================

        if (
            "total sales" in q
            or "sum sales" in q
            or "sales total" in q
            or "total sale" in q
            or "sum sale" in q
            or "sale total" in q
        ):

            return _sum_result(
                df,
                "Sales"
            )

        # ====================================================
        # COUNT
        # ====================================================

        if (
            "how many records" in q
            or "number of records" in q
            or "record count" in q
            or "count records" in q
        ):

            return _count_result(df)

        # ====================================================
        # CORRELATION
        # ====================================================

        if (
            "correlation" in q
            or "correlate" in q
        ):

            if (
                _mentions_tv(q)
                and _mentions_sales(q)
            ):

                return _correlation_result(
                    df,
                    "TV",
                    "Sales"
                )

            if (
                _mentions_radio(q)
                and _mentions_sales(q)
            ):

                return _correlation_result(
                    df,
                    "Radio",
                    "Sales"
                )

            if (
                _mentions_newspaper(q)
                and _mentions_sales(q)
            ):

                return _correlation_result(
                    df,
                    "Newspaper",
                    "Sales"
                )

        # ====================================================
        # UNIQUE VALUES
        # ====================================================

        if "unique" in q:

            if _mentions_sales(q):

                return _unique_result(
                    df,
                    "Sales"
                )

            if _mentions_tv(q):

                return _unique_result(
                    df,
                    "TV"
                )

            if _mentions_radio(q):

                return _unique_result(
                    df,
                    "Radio"
                )

            if _mentions_newspaper(q):

                return _unique_result(
                    df,
                    "Newspaper"
                )

        # ====================================================
        # GENERAL SUMMARY
        # ====================================================

        if (
            "summary" in q
            or "summarize" in q
            or "statistics" in q
            or "stats" in q
        ):

            return _dataset_summary(df)

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