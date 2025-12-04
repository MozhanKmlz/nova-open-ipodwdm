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

            try:
                tmp = self._as_json(self.rnc.temp_service_create())
            except Exception as e:
                # Inform user immediately, clean output
                return jsonify({
                    "error": "Temporary service creation failed",
                    "details": str(e)
                }), 400

            # 3) Activate terminals — MAY FAIL → MUST ROLLBACK
            try:
                act = self._as_json(self.ipsdnc.end_terminal_activation_request())
            except Exception as e:
                # --- ROLLBACK TEMPORARY OPTICAL TUNNEL ---
                try:
                    rollback = self._as_json(self.rnc.optical_tunnel_request_cancel())
                except Exception as re:
                    rollback = {"error": f"Rollback failed: {str(re)}"}
    
                return jsonify({
                    "error": "Activation failed",
                    "details": str(e),
                    "rollback": rollback,
                }), 400

            # ------------------------------------------------------------
            # Helper: Full rollback after activation
            # (used for service-create failure or power failures)
            # ------------------------------------------------------------
            def full_post_activation_rollback():
                results = {}
    
                # deactivate both A/Z terminals
                try:
                    results["deactivation"] = self._as_json(
                        self.ipsdnc.end_terminal_deactivation_request()
                    )
                except Exception as e:
                    results["deactivation_error"] = str(e)
    
                # cancel optical tunnel
                try:
                    results["optical_cancel"] = self._as_json(
                        self.rnc.optical_tunnel_request_cancel()
                    )
                except Exception as e:
                    results["optical_cancel_error"] = str(e)
    
                return results

            # ------------------------------------------------------------
            # 4) Service-create (rollback: deactivation + optical cancel)
            # ------------------------------------------------------------
            try:
                svc = self._as_json(self.rnc.service_create())
            except Exception as e:
                rollback = full_post_activation_rollback()
                return jsonify({
                    "error": "Service creation failed",
                    "details": str(e),
                    "rollback": rollback
                }), 400

            # 5) Power setup A (failure → rollback)
            try:
                pwrA = self._as_json(self.rnc.service_power_setup(which="A"))
            except Exception as e:
                try:
                    rollback = full_post_activation_rollback()
                except Exception as re:
                    rollback = {"error": f"Rollback failed: {str(re)}"}

                return jsonify({
                    "error": "Power setup failed at A-end",
                    "details": str(e),
                    "rollback": rollback
                }), 400

            # 6) Power setup Z (failure → rollback)
            try:
                pwrZ = self._as_json(self.rnc.service_power_setup(which="B"))
            except Exception as e:
                try:
                    rollback = full_post_activation_rollback()
                except Exception as re:
                    rollback = {"error": f"Rollback failed: {str(re)}"}

                return jsonify({
                    "error": "Power setup failed at Z-end",
                    "details": str(e),
                    "rollback": rollback
                }), 400
                
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


