def format_date(date_val) -> str:
    if hasattr(date_val, "strftime"):
        return date_val.strftime("%d-%b-%y")
    return str(date_val)

def round_dict_values(d: dict[str, float]) -> dict[str, int]:
    return {k: round(v) for k, v in d.items()}

def convert_bool(val) -> bool:
    return val=="TRUE"