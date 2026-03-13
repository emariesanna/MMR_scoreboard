def format_date(date_val) -> str:
    if hasattr(date_val, "strftime"):
        return date_val.strftime("%d-%b-%y")
    return str(date_val)

def round_dict_values(d: dict[str, float], decimals: int = 0) -> dict[str, int]:
    return {k: round(v, decimals) for k, v in d.items()}

def convert_bool(val) -> bool:
    return val=="TRUE"

def sum_dicts(dicts: list[dict[str, float]]) -> dict[str, float]:
    result = {}
    for d in dicts:
        for k, v in d.items():
            result[k] = result.get(k, 0) + v
    return result