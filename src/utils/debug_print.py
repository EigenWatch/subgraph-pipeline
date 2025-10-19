import pandas as pd


def debug_print(data, max_rows: int = 10):
    """Pretty-print data or pandas DataFrames with clear separators."""
    separator_top = ">>>" * 40
    separator_bottom = "<<<" * 40
    print(separator_top)

    if isinstance(data, pd.DataFrame):
        print(f"DataFrame ({len(data)} rows, {len(data.columns)} columns)")
        print("-" * 80)
        # Show top and bottom rows if large
        with pd.option_context(
            "display.max_rows", max_rows, "display.max_columns", None
        ):
            if len(data) > max_rows:
                print(data.head(max_rows // 2))
                print("...")
                print(data.tail(max_rows // 2))
            else:
                print(data)
    elif isinstance(data, (dict, list)):
        import json

        print(json.dumps(data, indent=2, default=str))
    else:
        print(data)

    print(separator_bottom)
