# controllers/base_rnc.py
import os, time, json, logging, requests, paramiko, xml.etree.ElementTree as ET
from queue import Empty
from flask import jsonify, Response
from controllers.rnc import RNCController
from utility.utils import safe_extract_data

logger = logging.getLogger(__name__)

JSON_HEADERS = {"Content-Type":"application/json"}

class ConcreteRNCController(RNCController):
    def __init__(self, config):
        super().__init__(config)
        required = ["host","restconf_port","rest_user","rest_pass"]
        missing = [k for k in required if k not in self.config or not self.config[k]]
        if missing:
            raise ValueError(f"rnc.conf missing keys: {', '.join(missing)}")
        self._session = requests.Session()
        self._session.auth = (self.config["rest_user"], self.config["rest_pass"])
        self._session.headers.update({"Content-Type":"application/json","Accept":"application/json"})
        self._connect_timeout  = int(self.config.get("connect_timeout", 5))
        self._timeout          = int(self.config.get("timeout", 60))
        self._timeout_heavy    = int(self.config.get("timeout_heavy", 180))
        logger.info(
            "RNC timeouts set",
            extra={"connect": self._connect_timeout, "quick": self._timeout, "heavy": self._timeout_heavy}
        )

    @property
    def _t_quick(self):
        return (self._connect_timeout, self._timeout)

    @property
    def _t_heavy(self):
        return (self._connect_timeout, self._timeout_heavy)

    def _resp_to_dict(self, resp):
        if isinstance(resp, tuple):
            resp = resp[0]
        if isinstance(resp, Response):
            try:
                return json.loads(resp.get_data(as_text=True) or "{}")
            except Exception:
                logger.exception("Failed to decode Flask Response to JSON")
                return {}
        if isinstance(resp, dict):
            return resp
        try:
            return json.loads(str(resp))
        except Exception:
            return {}

    def _err(self, msg: str, status: int = 400) -> Response:
        resp = jsonify({"error": msg})
        resp.status_code = status
        return resp

    def connect_to_tpce(self):
        """
        Establish connection path to TPCE.
        Returns (ssh_client_or_None, local_port_effective, tpce_host)
        - direct mode: no SSH, returns (None, restconf_port, host)
        - tunnel mode: returns (ssh_client, local_forward_port, host)
        """
        mode = (self.config.get("mode") or "tunnel").lower()
        host = self.config["host"]
        if mode == "direct":
            port = int(self.config.get("restconf_port", 8181))
            return None, port, host
        # tunnel mode
        ssh = self._ensure_tunnel()
        local_port = int(self.config.get("local_port", 8181))
        return ssh, local_port, host


    # -------- connection helpers --------
    def _rest_base(self):
        mode = (self.config.get("mode") or "tunnel").lower()
        if mode == "direct":
            host = self.config["host"]
            port = int(self.config.get("restconf_port", 8181))
            return f"http://{host}:{port}"
        # tunnel mode base is always localhost:local_port
        port = int(self.config.get("local_port", 8181))
        return f"http://127.0.0.1:{port}"

    def _ensure_tunnel(self):
        """No-op in direct mode. In tunnel mode, establish/refresh SSH port forward."""
        mode = (self.config.get("mode") or "tunnel").lower()
        if mode == "direct":
            return None  # nothing to do

        tpce_host = self.config["host"]
        tpce_port = int(self.config.get("ssh_port", 22))
        tpce_user = self.config.get("username")
        tpce_pass = self.config.get("password")
        local_port = int(self.config.get("local_port", 8181))
        remote_rest = int(self.config.get("restconf_port", 8181))

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(tpce_host, tpce_port, tpce_user, tpce_pass, timeout=10)
        except paramiko.AuthenticationException:
            logger.error("Authentication failed (SSH to TPCE). Check username/password.")
            raise
        except Exception:
            logger.exception("SSH connect error")
            raise

        transport = ssh.get_transport()
        transport.open_channel(
            "direct-tcpip",
            (tpce_host, remote_rest),   # remote destination
            ("127.0.0.1", local_port),  # local origin
        )
        return ssh  # caller may ignore, GC will close when object dies

    # -------- RNC operations --------
    def temp_service_create(self):
        tpce_log = []
        try:
            logger.info("Temporary service creation RPC called ...")
            ssh = self._ensure_tunnel()

            base = self._rest_base()
            url = f"{base}/rests/operations/org-openroadm-service:temp-service-create"

            payload = self._render_json("IC_SRG1_PP1.temp_service_create")

            r = self._session.post(url, json=payload, timeout=self._timeout)
            r.raise_for_status()
            data = r.json()
            msg = data.get("org-openroadm-service:output", {}) \
                      .get("configuration-response-common", {}) \
                      .get("response-message")
            logger.info(f"Temporary Service creation response: {msg}")
            tpce_log.append(msg)

            try:
                from kafka_notif.NBInotif import message_queue
                kafka_message = message_queue.get(timeout=120)
                logger.info(f"Kafka message received: {kafka_message}")
                tpce_log.append(f"Kafka: {kafka_message}")
            except Empty:
                logger.error("Timeout waiting for Kafka message.")
                tpce_log.append("Timeout waiting for Kafka message.")

            logger.info("Checking for updated temporary service list...")
            temp_list_resp = self.temp_service_list()
            temp_list_resp_data = self._resp_to_dict(temp_list_resp)
            logger.info(f"Updated temp service list: {temp_list_resp_data}")
            tpce_log.append(temp_list_resp_data)

            return jsonify({"create_temp_service_response": data, "tpce_log": tpce_log})

        except requests.HTTPError as e:
            logger.error(f"Failed to process the request: {e}")
            logger.error("REST error %s: %s", e.response.status_code, e.response.text)
            return self._err(f"REST {e.response.status_code}: {e.response.reason}", 400)
        except Exception as e:
            logger.error(f"TEMP SERVICE CREATE FAILED — PROCESS ABORTED: {e}")
            raise RuntimeError(f"temp-service-create failed: {str(e)}")

    def temp_service_list(self):
        try:
            self._ensure_tunnel()
            base = self._rest_base()
            url = f"{base}/rests/data/org-openroadm-service:temp-service-list"
            r = self._session.get(url, timeout=self._t_quick)
            r.raise_for_status()
            return jsonify(r.json())
        except requests.HTTPError as e:
            logger.error("REST error %s: %s", e.response.status_code, e.response.text)
            return jsonify({"error": f"REST {e.response.status_code}", "details": e.response.text}), 400
        except Exception as e:
            logger.error(e)
            return jsonify({"error": str(e)}), 400

    def service_power_setup(self, which: str):
        try:
            if which == "A":
                logging.info("A End terminal power controller RPC called...")
            else:
                logging.info("Z End terminal power controller RPC called...")

            self._ensure_tunnel()
            base = self._rest_base()
            url = f"{base}/rests/operations/transportpce-olm:service-power-setup"
            payload = (self._render_json("IC_SRG1_PP1.end_terminal_power_control_A")
                    if which == "A"
                    else self._render_json("IC_SRG1_PP1.end_terminal_power_control_B"))
            r = self._session.post(url, json=payload, timeout=self._t_heavy)
            r.raise_for_status()
            return jsonify(r.json())
        except requests.HTTPError as e:
            logger.error("REST error %s: %s", e.response.status_code, e.response.text)
            return jsonify({"error": f"REST {e.response.status_code}", "details": e.response.text}), 400
        except Exception as e:
            logger.error(f"Failed to process the request: {e}")
            return jsonify({"error": str(e)}), 400

    def service_create(self):
        tpce_log = []
        try:
            logger.info("Service creation RPC called ...")
            self._ensure_tunnel()
            base = self._rest_base()
            url = f"{base}/rests/operations/org-openroadm-service:service-create"
            r = self._session.post(url, json=self._render_json("IC_SRG1_PP1.service_create"), timeout=self._timeout)
            r.raise_for_status()
            data = r.json()
            msg = data.get("org-openroadm-service:output", {}) \
                      .get("configuration-response-common", {}) \
                      .get("response-message")
            logger.info(f"Service creation response: {msg}")
            tpce_log.append(msg)

            try:
                from kafka_notif.NBInotif import message_queue
                kafka_message = message_queue.get(timeout=120)
                logger.info(f"Kafka message received: {kafka_message}")
                tpce_log.append(f"Kafka notification: {kafka_message}")
            except Empty:
                logger.error("Timeout waiting for Kafka message.")
                tpce_log.append("Timeout waiting for Kafka message.")

            logger.info("Checking for updated service list...")
            svc_list_resp = self.service_list()
            svc_list_resp_data = self._resp_to_dict(svc_list_resp)
            tpce_log.append(svc_list_resp_data)
            logger.info(f"Updated service list: {svc_list_resp_data}")

            return jsonify({"create_service_response": data, "tpce_log": tpce_log})

        except requests.HTTPError as e:
            logger.error("REST error %s: %s", e.response.status_code, e.response.text)
            return jsonify({"error": f"REST {e.response.status_code}", "details": e.response.text}), 400
        except Exception as e:
            logger.error(f"Failed to process the request: {e}")
            return jsonify({"error": str(e)}), 400

    def service_list(self):
        try:
            self._ensure_tunnel()
            base = self._rest_base()
            url = f"{base}/rests/data/org-openroadm-service:service-list"
            r = self._session.get(url, timeout=self._t_quick)
            r.raise_for_status()
            return jsonify(r.json())
        except requests.HTTPError as e:
            logger.error("REST error %s: %s", e.response.status_code, e.response.text)
            return jsonify({"error": f"REST {e.response.status_code}", "details": e.response.text}), 400
        except Exception as e:
            logger.error(e)
            return jsonify({"error": str(e)}), 400

    def optical_tunnel_request_cancel(self):
        try:
            logger.info("Optical tunnel request cancel RPC called ...")
            self._ensure_tunnel()
            base = self._rest_base()
            url = f"{base}/rests/operations/org-openroadm-service:temp-service-delete"
            r = self._session.post(url, json=self._render_json("IC_SRG1_PP1.optical_tunnel_request_cancel"), timeout=self._timeout)
            r.raise_for_status()
            return jsonify(safe_extract_data(r.json()))
        except requests.HTTPError as e:
            logger.error("REST error %s: %s", e.response.status_code, e.response.text)
            return jsonify({"error": f"REST {e.response.status_code}", "details": e.response.text}), 400
        except Exception as e:
            logger.error(f"Failed to process the request: {e}")
            return jsonify({"error": str(e)}), 400

    def service_delete(self):
        try:
            logger.info("Service deletion RPC called ...")

            self._ensure_tunnel()
            base = self._rest_base()
            url = f"{base}/rests/operations/org-openroadm-service:service-delete"
            r = self._session.post(url, json=self._render_json("IC_SRG1_PP1.service_delete"), timeout=self._timeout)
            r.raise_for_status()
            data = safe_extract_data(r.json())

            if data:
                response_message = data.get("org-openroadm-service:output", {}) \
                    .get("configuration-response-common", {}) \
                    .get("response-message", "No message")
                logger.info(f"Service deletion response: {response_message}")
            else:
                logger.info("Failed to retrieve JSON data from the response.")

            return jsonify(data)

        except requests.HTTPError as e:
            logger.error("REST error %s: %s", e.response.status_code, e.response.text)
            return jsonify({"error": f"REST {e.response.status_code}", "details": e.response.text}), 400
        except Exception as e:
            logger.error(f"Failed to process the request: {e}")
            return jsonify({"error": str(e)}), 400


