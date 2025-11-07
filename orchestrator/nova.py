# orchestrator/nova.py
from flask import Blueprint, request, jsonify, Response
import json, os, logging
from rich.console import Console
from rich.panel import Panel
from rich.align import Align

class NOVAOrchestrator:
    def __init__(self, ipsdnc_ctrl, rnc_ctrl, kafka_consumer_fn=None):
        self.ipsdnc = ipsdnc_ctrl
        self.rnc    = rnc_ctrl
        self._consumer_fn = kafka_consumer_fn

        self.bp = Blueprint("nova", __name__)
        self.bp.add_url_rule("/create-service", "create_service", self.create_service, methods=["POST"])
        self.bp.add_url_rule("/delete-service", "delete_service", self.delete_service, methods=["POST"])

        if self._consumer_fn:
            import threading
            threading.Thread(target=self._consumer_fn, daemon=True).start()

        self.print_logo()

    def _as_json(self, resp):
        if resp is None:
            return {}
        # 1) unwrap (Response, status[, headers])
        if isinstance(resp, tuple):
            resp = resp[0]
        # 2) dict passthrough
        if isinstance(resp, dict):
            return resp
        # 3) Flask Response
        if isinstance(resp, Response):
            if getattr(resp, "is_json", False):
                try:
                    return resp.get_json()
                except Exception:
                    pass
            try:
                return json.loads(resp.get_data(as_text=True) or "{}")
            except Exception:
                logging.exception("Failed to parse JSON response")
                return {}
        # 4) last resort
        try:
            return json.loads(str(resp))
        except Exception:
            return {}

    def print_logo(self):
        console = Console()
        banner = "\n".join([
            "N     N   OOOO  V       V    A      ",
            "NN    N  O    O  V     V    A A     ",
            "N N   N  O    O   V   V    A   A    ",
            "N  N  N  O    O    V V    AAAAAAA   ",
            "N   N N  O    O     V    A       A  ",
            "N    NN   OOOO      V    A       A  ",
        ])
        colored = f"[#def2f1]{banner}[/#def2f1]"
        panel = Panel(
            Align.center(colored),
            title="🌐 NOVA",
            subtitle="\nNetwork Orchestration, Vigilance & Automation — v1.0\n Moojan Kamalzadeh",
            border_style="#3aafa9",
            width=60,
        )
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            console.print(panel, justify="left")
        logging.info("🚀 NOVA startup complete, ready to orchestrate your network.")

    def create_service(self):
        data = request.get_json() or {}
        try:
            # 1) performance info
            eti = self._as_json(self.ipsdnc.end_terminal_performance_info_request())

            # 2) temp service
            tmp = self._as_json(self.rnc.temp_service_create())

            # 3) activation (reads JSON from the *current* request)
            act = self._as_json(self.ipsdnc.end_terminal_activation_request())

            # 4) real service-create
            svc = self._as_json(self.rnc.service_create())

            # 5) power setups
            pwrA = self._as_json(self.rnc.service_power_setup(which="A"))
            pwrZ = self._as_json(self.rnc.service_power_setup(which="B"))

            return jsonify({
                "end_terminal_performance_info":   eti,
                "temporary_service_creation":      tmp,
                "end_terminal_activation":         act,
                "service_creation":                svc,
                "end_terminal_power_control_A":    pwrA,
                "end_terminal_power_control_Z":    pwrZ,
            })
        except Exception as e:
            logging.exception("create_service failed")
            return jsonify({"error": str(e)}), 500

    def delete_service(self):
        data = request.get_json() or {}
        try:
            # 1) deactivate (reads JSON from current request)
            deact = self._as_json(self.ipsdnc.end_terminal_deactivation_request())
            # 2) delete
            deleted = self._as_json(self.rnc.service_delete())
            return jsonify({
                "end_terminal_deactivation": deact,
                "service_deletion":          deleted,
            })
        except Exception as e:
            logging.exception("delete_service failed")
            return jsonify({"error": str(e)}), 500

