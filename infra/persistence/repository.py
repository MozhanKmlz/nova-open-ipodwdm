from typing import Optional, Tuple, Dict, Any
from pymongo import MongoClient
from string import Template

class PayloadNotFound(KeyError):
    pass

class PayloadRepository:
    def __init__(self, mongo_url: str, db_name: str = "nova_database", coll: str = "payloads") -> None:
        self._client = MongoClient(mongo_url)
        self._col = self._client[db_name][coll]
        self._cache: Dict[str, str] = {}

    def get(self, name: Optional[str] = None, vendor: Optional[str] = None, action: Optional[str] = None) -> str:
        cache_key = self._make_cache_key(name=name, vendor=vendor, action=action)
        if cache_key in self._cache:
            return self._cache[cache_key]
        payload, _doc = self._fetch_payload(name=name, vendor=vendor, action=action)
        self._cache[cache_key] = payload
        return payload

    def render(self, name: Optional[str] = None, vendor: Optional[str] = None,
               action: Optional[str] = None, **vars: Any) -> str:
        raw = self.get(name=name, vendor=vendor, action=action)
        if "${" in raw:
            return Template(raw).safe_substitute({k: str(v) for k, v in vars.items()})
        try:
            return raw.format(**{k: str(v) for k, v in vars.items()})
        except KeyError:
            rendered = raw
            for k, v in vars.items():
                rendered = rendered.replace("{" + k + "}", str(v))
            return rendered

    def _make_cache_key(self, name: Optional[str], vendor: Optional[str], action: Optional[str]) -> str:
        if name: return name.lower().strip()
        if vendor and action: return f"{vendor.lower().strip()}.{action.lower().strip()}"
        raise PayloadNotFound("Provide either name='vendor.action' or vendor='x', action='y'")

    def _fetch_payload(self, name: Optional[str], vendor: Optional[str], action: Optional[str]) -> Tuple[str, Dict[str, Any]]:
        if name:
            q = {"$or": [{"name": name}, {"key": name}]}
            doc = self._col.find_one(q) or (("." in name) and
                    self._col.find_one({"vendor": name.split(".",1)[0], "action": name.split(".",1)[1]}))
            if not doc:
                raise PayloadNotFound(f"Payload '{name}' not found in Mongo")
            return self._extract_payload_field(doc, default_key=name), doc
        if vendor and action:
            doc = self._col.find_one({"vendor": vendor, "action": action}) or \
                  self._col.find_one({"key": f"{vendor}.{action}"})
            if not doc:
                raise PayloadNotFound(f"Payload '{vendor}.{action}' not found in Mongo")
            return self._extract_payload_field(doc, default_key=f"{vendor}.{action}"), doc
        raise PayloadNotFound("Provide either name='vendor.action' or vendor/action pair")

    @staticmethod
    def _extract_payload_field(doc: Dict[str, Any], default_key: str) -> str:
        for field in ("payload", "xml", "content"):
            val = doc.get(field)
            if isinstance(val, str) and val.strip():
                return val
            if isinstance(val, dict):            
                return json.dumps(val)
        raise PayloadNotFound(f"Document found for '{default_key}', but no payload/xml/content field was present")
