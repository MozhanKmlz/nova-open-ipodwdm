import configparser
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def _norm_vendor_block(name, sec):
    d = {k.lower(): v for k, v in sec.items()}
    if name == "nec":
        # normalize NEC keys to routerA/routerB naming your code expects
        d["routera_ip"]   = d.pop("mpdra_ip",   d.get("routera_ip", ""))
        d["routera_user"] = d.pop("mpdra_user", d.get("routera_user", ""))
        d["routera_pass"] = d.pop("mpdra_pass", d.get("routera_pass", ""))
        d["routerb_ip"]   = d.pop("mpdrz_ip",   d.get("routerb_ip", ""))
        d["routerb_user"] = d.pop("mpdrz_user", d.get("routerb_user", ""))
        d["routerb_pass"] = d.pop("mpdrz_pass", d.get("routerb_pass", ""))
    return d

def load_ipsdnc_config(path: str="config/ipsdnc.conf"):
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} missing—copy ipsdnc.conf.example and fill in real values")
    cfg = configparser.ConfigParser()
    cfg.read(path)

    base = {
        "vendor":   (cfg["default"].get("vendor","") or "").strip().lower(),
        "mongo_url": cfg["default"]["mongo_url"],
        "oper_mode": cfg["default"].get("oper_mode"),
        "vendors": {}
    }

    for sec in cfg.sections():
        name = sec.strip().lower()
        if name in ("default",):
            continue
        base["vendors"][name] = _norm_vendor_block(name, cfg[sec])

    # For convenience, also expose the active vendor block at top-level:
    active = base["vendor"]
    if active and active in base["vendors"]:
        base.update(base["vendors"][active])

    logger.debug("Active vendor: %s", active)
    logger.debug("Vendors available: %s", list(base["vendors"].keys()))
    return base
    
def _read_ini_lower(path: str) -> dict:
    """
    Read an INI file and return a dict of sections -> dict of options,
    with all keys normalized to lowercase (to avoid configparser case issues).
    """
    ini = configparser.ConfigParser()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{path} not found")
    ini.read(path)

    out = {}
    for section in ini.sections():
        sec = {}
        for k, v in ini.items(section):
            # ini already lowercases keys by default; enforce to be safe
            sec[k.lower()] = v.strip()
        out[section.lower()] = sec
    # include DEFAULT if present (ConfigParser’s DEFAULTSECT)
    if ini.defaults():
        out.setdefault("default", {})
        for k, v in ini.defaults().items():
            out["default"][k.lower()] = v.strip()
    return out

def _require(d: dict, keys: list, section_hint: str = ""):
    missing = [k for k in keys if d.get(k) in (None, "")]
    if missing:
        hint = f" in {section_hint}" if section_hint else ""
        raise ValueError(f"Missing required vendor keys{hint}: {', '.join(missing)}")

def _require_values(named_values: dict, section_hint: str = ""):
    missing = [name for name, val in named_values.items() if val in (None, "")]
    if missing:
        hint = f" in {section_hint}" if section_hint else ""
        raise ValueError(f"Missing required vendor keys{hint}: {', '.join(missing)}")

def load_rnc_config(path: str="config/rnc.conf"):
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} missing—copy rnc.conf.example and fill in real values")
    cfg = configparser.ConfigParser()
    cfg.read(path)
    d = {}
    d.update(cfg["tpce"])
    d.update(cfg["rest"])
    return d

def load_kafka_config(path: str = "config/kafka.conf"):
    """
    Load Kafka consumer config from an INI file.
    Returns a dict with typed values and sensible defaults.
    """
    exists = Path(path).exists()
    logger.debug(f"Loading Kafka config from {path} (exists={exists})")
    if not exists:
        raise FileNotFoundError(f"{path} missing—copy kafka.conf.example and fill in real values")

    cfg = configparser.ConfigParser()
    cfg.read(path)

    if "default" not in cfg:
        raise ValueError(f"{path} missing [default] section")

    s = cfg["default"]

    # Typed getters with defaults
    def _getbool(key, default):
        try:
            return s.getboolean(key, fallback=default)
        except ValueError:
            logger.warning("Invalid bool for %s in %s; using default=%s", key, path, default)
            return default

    def _getfloat(key, default):
        try:
            return s.getfloat(key, fallback=default)
        except ValueError:
            logger.warning("Invalid float for %s in %s; using default=%s", key, path, default)
            return default

    d = {
        "enabled":           _getbool("enabled", True),
        "broker":            s.get("broker", "localhost:9092"),
        "topic":             s.get("topic", ""),
        "group_id":          s.get("group_id", "nova"),
        "auto_offset_reset": s.get("auto_offset_reset", "latest"),
        "poll_interval":     _getfloat("poll_interval", 1.0),
    }

    # Quick sanity logs
    redacted = {**d, "broker": d["broker"], "group_id": d["group_id"]}
    logger.debug("Kafka config loaded: %s", redacted)

    # Minimal validation
    missing = [k for k in ("broker", "topic", "group_id") if not d.get(k)]
    if missing and d["enabled"]:
        raise ValueError(f"kafka.conf missing keys: {', '.join(missing)}")

    return d

