import importlib
from flask import Flask, request
from utility.config_loader import load_ipsdnc_config, load_rnc_config, load_kafka_config
from utility.utils import *
from controllers.base_ipsdnc import ConcreteIPSDNCController
from controllers.base_rnc import ConcreteRNCController
from orchestrator.nova import NOVAOrchestrator
from kafka_notif.NBInotif import start_kafka_consumer
from routes.ipsdnc_interactions import create_ipsdnc_bp
from routes.rnc_interactions import create_rnc_bp

class VendorDispatchIPSDNC:
    def __init__(self, base_cfg):
        self.base_cfg = base_cfg
        self._cache = {}
        self._default_vendor = (base_cfg.get("vendor") or "cisco").strip().lower()

    def _resolve_class(self, dotted: str):
        if not dotted:
            return ReleaseAwareIPSDNCController
        try:
            mod, cls = dotted.rsplit(".", 1)
            return getattr(importlib.import_module(mod), cls)
        except Exception:
            # fallback so a bad config doesn’t break the app
            return ReleaseAwareIPSDNCController

    def _get_controller(self):
        body = request.get_json(silent=True) or {}
        vendor = (body.get("vendor") or self._default_vendor).strip().lower()
        if vendor in self._cache:
            return self._cache[vendor]

        cfg = dict(self.base_cfg)
        cfg["vendor"] = vendor
        cfg["allow_vendor_override"] = False
        vendor_section = cfg.get("vendors", {}).get(vendor, {})
        dotted = vendor_section.get("controller_class")
        cls = self._resolve_class(dotted)

        ctrl = cls(cfg)
        self._cache[vendor] = ctrl
        return ctrl

    def end_terminal_performance_info_request(self):
        ctrl = self._get_controller()
        fn = getattr(ctrl, "end_terminal_performance_info_request", None)
        if not callable(fn):
            # This gives you a clear error instead of silently calling the wrong thing
            raise RuntimeError(
                f"{type(ctrl).__name__} is missing end_terminal_performance_info_request()"
            )
        return fn()
    def end_terminal_activation_request(self):   return self._get_controller().end_terminal_activation_request()
    def end_terminal_deactivation_request(self): return self._get_controller().end_terminal_deactivation_request()
    def show_target_output_power(self):          return self._get_controller().show_target_output_power()

logger = setup_logger()
app = Flask(__name__)

ipsdnc_cfg = load_ipsdnc_config()
rnc_cfg    = load_rnc_config()
kafka_cfg  = load_kafka_config()

ipsdnc_ctrl  = VendorDispatchIPSDNC(ipsdnc_cfg)
rnc_ctrl     = ConcreteRNCController(rnc_cfg)

app.register_blueprint(create_ipsdnc_bp(ipsdnc_ctrl))
app.register_blueprint(create_rnc_bp(rnc_ctrl))

nova = NOVAOrchestrator(ipsdnc_ctrl, rnc_ctrl)
app.register_blueprint(nova.bp)

if __name__ == "__main__":
    import os
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_kafka_consumer(kafka_cfg)
    app.run(host="0.0.0.0", port=5000, debug=True)
