import time, json
import logging
import socket
import subprocess
from ncclient.xml_ import to_ele
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any
from flask import request, jsonify
from ncclient import manager
from utility.utils import safe_extract_data, get_operational_mode_info
from controllers.ipsdnc import IPSDNCController
from infra.persistence.repository import PayloadRepository, PayloadNotFound
from utility.oc_lookup import OpenConfigLookup

logger = logging.getLogger(__name__)
TD_NS = {"td": "http://openconfig.net/yang/terminal-device"}


class ConcreteIPSDNCController(IPSDNCController):
    """
    Implements the OpenConfig RPCs once using the Template Method pattern.
    Subclasses override only connection hooks and optional vendor hooks.
    """

    def __init__(self, config: dict):
        logger.info("[Init] Initializing ConcreteIPSDNCController...")
        super().__init__(config)
        self.config = config
        self.default_oper_mode = config.get("oper_mode")
        self.oper_mode = self.default_oper_mode
        self.payloads = PayloadRepository(config["mongo_url"])
        self.vendor = (config.get("vendor") or "").strip().lower()
        self.allow_vendor_override = bool(config.get("allow_vendor_override", True))
        self.component_name = config.get("component_name", "")
        self.vendor_cfgs = config.get("vendors", {})
        self.default_component_name = config.get("component_name_default", "")
        self._apply_vendor_endpoints(self.vendor)

        self._logged_revisions = set()
        self.oc_lookup = OpenConfigLookup()

        for ip in (self.ipA, self.ipB):
            if ip:
                # logger.info("[Init] Ensuring OpenConfig capabilities cache for %s", ip)
                self._ensure_oc_caps(ip)

    def _apply_vendor_endpoints(self, v: str):
        logger.info("[Vendor] Applying vendor endpoints for '%s'", v)
        v = (v or "").strip().lower()
        b = self.vendor_cfgs.get(v, {})

        def pick(*names):
            for n in names:
                if b.get(n) is not None:
                    return b.get(n)
            return None

        self.ipA = pick("routera_ip", "mpdra_ip")
        self.ipB = pick("routerb_ip", "mpdrz_ip")
        self._credA = (pick("routera_user", "mpdra_user"), pick("routera_pass", "mpdra_pass"))
        self._credB = (pick("routerb_user", "mpdrz_user"), pick("routerb_pass", "mpdrz_pass"))

        self.jump_host = b.get("jump_host")
        self.jump_user = b.get("jump_user")
        self.jump_pass = b.get("jump_pass")

        try:
            self.jump_port = int(b.get("jump_port", 22))
        except Exception:
            self.jump_port = 22

        self.oper_mode = b.get("oper_mode", self.default_oper_mode)

        logger.debug("[Vendor] Applied vendor=%s -> A=%s, B=%s", v, self.ipA, self.ipB)

    def _normalize_body(self):
        logger.info("[Body] Normalizing request body...")
        body = request.get_json(silent=True) or {}
        v = (body.get("vendor") or "").strip().lower()
        if v and v != self.vendor and self.allow_vendor_override:
            logger.info("[Body] Vendor override detected: %s (was %s)", v, self.vendor)
            self.vendor = v
            self._apply_vendor_endpoints(self.vendor)
        comp = body.get("component-name") or body.get("component_name") or self.default_component_name
        freq = body.get("frequency")
        pwr = body.get("TxPower", body.get("target_output_power"))
        logger.debug("[Body] comp=%s, freq=%s, pwr=%s", comp, freq, pwr)
        return body, comp, freq, pwr

    def _get_device_capabilities(self, ip: str):
        logger.info("[Caps] Fetching device capabilities from %s", ip)
        try:
            with self._connect(ip) as m:
                caps = list(m.server_capabilities)
                logger.debug("[Caps] Raw capabilities from %s: %s", ip, caps)
        except Exception as e:
            logger.warning("[Caps] Could not fetch capabilities from %s: %s", ip, e)
            return {}
        oc_caps = [c for c in caps if "openconfig" in c]
        parsed = self._parse_oc_modules(oc_caps)
        logger.info("[Caps] Parsed OpenConfig modules for %s: %s", ip, parsed)
        return parsed

    def _parse_oc_modules(self, caps):
        result = {}
        for c in caps:
            if "module=" in c:
                mod = rev = None
                parts = c.split("?")[-1].split("&")
                for p in parts:
                    if p.startswith("module="):
                        mod = p.split("=")[1]
                    elif p.startswith("revision="):
                        rev = p.split("=")[1]
                if mod:
                    result[mod] = {"revision": rev}
        return result

    def _get_oc_revision(self, module: str, ip: str):
        rev = None
        try:
            self._ensure_oc_caps(ip)
            entry = self._oc_caps_cache[ip].get(module)
            rev = entry.get("revision") if isinstance(entry, dict) else entry
            logger.debug("[OC] Revision for %s on %s: %s", module, ip, rev)
        except Exception as e:
            logger.warning("[OC] Failed to get revision for %s on %s: %s", module, ip, e)
        return rev

    def _get_oc_version(self, module: str, ip: str):
        self._ensure_oc_caps(ip)
        entry = self._oc_caps_cache[ip].get(module)
        if isinstance(entry, dict):
            if module == "openconfig-platform":
                if entry.get("version"):
                    logger.debug("[OC] Version for %s on %s: %s", module, ip, entry["version"])
                    return entry["version"]
                rev = entry.get("revision")
                mapped = self.oc_lookup.get_version_by_revision(module, rev) if rev else None
                logger.debug("[OC] Mapped revision %s -> version %s", rev, mapped or rev)
                return mapped or rev
            return entry.get("revision")
        return entry

    def _ensure_oc_caps(self, ip: str):
        if not hasattr(self, "_oc_caps_cache"):
            self._oc_caps_cache = {}
        if ip in self._oc_caps_cache:
            return

        logger.info("[Capabilities] Ensuring OpenConfig capabilities for %s", ip)
        try:
            with self._connect(ip) as m:
                caps = list(m.server_capabilities)
                oc_caps = [c for c in caps if "openconfig" in c]
                parsed = self._parse_oc_modules(oc_caps)
                if any("ietf-netconf-monitoring" in c for c in caps):
                    for mod in parsed.keys():
                        try:
                            rpc = f"""
                            <get-schema xmlns="urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring">
                                <identifier>{mod}</identifier>
                                <format>yang</format>
                            </get-schema>
                            """
                            rsp = m.dispatch(to_ele(rpc))
                            xml = rsp.xml
                            mobj = re.search(r'oc-ext:openconfig-version\s+"([^"]+)"', xml)
                            if mobj:
                                parsed[mod]["version"] = mobj.group(1)
                                logger.debug("[Caps] Found version %s for %s", parsed[mod]["version"], mod)
                        except Exception as inner_e:
                            logger.debug("[Caps] Skipping get-schema for %s on %s: %s", mod, ip, inner_e)
                self._oc_caps_cache[ip] = parsed
                logger.info("✅ Cached OC capabilities for %s: %s", ip, parsed)
        except Exception as e:
            logger.warning("[Caps] Could not fetch capabilities from %s: %s", ip, e)
            self._oc_caps_cache[ip] = {}

    def _render_payload(self, short_name: str, **kwargs) -> str:
        ip = kwargs.get("ip", self.ipA)
        module = "openconfig-platform"
        ver = self._get_oc_version(module, ip)
        rev = self._get_oc_revision(module, ip)
        logger.info("[Payload] Rendering payload '%s'", short_name)

        # Log once per module+version/revision
        if short_name in ("set_power_and_frequency", "read_target_output_power"):
            key = (module, ver or rev)
            if key not in getattr(self, "_logged_revisions", set()):
                tag = self.oc_lookup.get_tag_for_version(ver) if ver else None
                if ver:
                    if tag:
                        logger.info(
                            "[Payload] Using %s\n"
                            "    • OpenConfig release version : %s\n"
                            "    • Module version             : %s\n"
                            "    • Module revision date       : %s",
                            module, tag, ver, rev
                        )
                    else:
                        logger.info(
                            "[Payload] Using %s\n"
                            "    • Module version             : %s\n"
                            "    • Module revision date       : %s",
                            module, ver, rev
                        )
                else:
                     logger.info(
                        "[Payload] Using %s\n"
                        "    • Module revision date       : %s",
                        module, rev
                    )
                self._logged_revisions.add(key)

        logger.debug("[Payload] Falling back to common.%s", short_name)
        return self.payloads.render(name=f"common.{short_name}", **kwargs)

    def _render_json(self, short_name: str):
        raw = self._render_payload(short_name)
        logger.debug("[Payload] JSON render for %s: %s chars", short_name, len(raw))
        return json.loads(raw)

    def _connect(self, ip: str):
        u, p = self._credA if ip == self.ipA else self._credB
        if getattr(self, "jump_host", None):
            logger.info("[Connect] Using jump host %s -> %s", self.jump_host, ip)
            lp = self._ensure_tunnel(ip, 830)
            return manager.connect(
                host="localhost", port=lp, username=u, password=p,
                hostkey_verify=False, look_for_keys=False, allow_agent=False, timeout=30
            )
        logger.info("[Connect] Direct NETCONF connect to %s", ip)
        return manager.connect(
            host=ip, port=830, username=u, password=p,
            hostkey_verify=False, look_for_keys=False, allow_agent=False, timeout=200
        )

    def _parse_target_output_power(self, xml: str):
        try:
            node = ET.fromstring(xml).find(".//td:target-output-power", TD_NS)
        except Exception as e:
            logger.error("[Parse] Error parsing target-output-power: %s", e)
            return None, f"parse error: {e}"
        if node is None or node.text is None:
            return None, "target-output-power not found"
        try:
            return float(node.text), None
        except Exception:
            logger.error("[Parse] Invalid target-output-power '%s'", node.text)
            return None, f"invalid target-output-power '{node.text}'"

    def set_power_and_frequency(self, *, ip: str, component_name: str, frequency, tx_power) -> dict:
        logger.info("[RPC] set_power_and_frequency called on %s", ip)
        xml = self._render_payload(
            "set_power_and_frequency",
            ip=ip, component_name=component_name,
            frequency=frequency, target_output_power=tx_power,
        )
        logger.debug("[RPC] XML payload length=%s", len(xml))
        with self._connect(ip) as m:
            m.edit_config(target="candidate", config=xml)
            m.commit()
        logger.info("[RPC] set_power_and_frequency applied successfully on %s", ip)
        return {"message": "Target output power and frequency changed successfully"}

    def read_target_output_power(self, *, ip: str, component_name: str) -> dict:
        logger.info("[RPC] read_target_output_power called on %s", ip)
        flt = self._render_payload("read_target_output_power", component_name=component_name)
        with self._connect(ip) as m:
            xml = m.get_config(source="running", filter=("subtree", flt)).data_xml
        val, err = self._parse_target_output_power(xml)
        if err:
            logger.warning("[RPC] Error reading target_output_power on %s: %s", ip, err)
            return {"error": err}
        logger.info("[RPC] target_output_power on %s = %s dBm", ip, val)
        return {"target_output_power": val}

    def end_terminal_performance_info_request(self):
        try:
            logger.info("[RPC] End Terminal Performance Info Request")
            perf = self._render_json("et_performance_info_req")
            rid = perf["input"]["sdnc-request-header"]["request-id"]
            op = get_operational_mode_info()
            resp = { ... }  # unchanged
            data = safe_extract_data(resp)
            info = data.get("output", {}).get("a-z-end-common-interface-characteristics", {})
            logger.info("[RPC] Perf Info: oper_mode=%s, min_freq=%s, max_freq=%s",
                        info.get("supported-operational-modes", [{}])[0].get("operational-mode-id"),
                        info.get("min-frequency"), info.get("max-frequency"))
            return jsonify(data)
        except Exception as e:
            logger.exception("[RPC] ET performance info failed: %s", e)
            return jsonify({"error": str(e)}), 500

    def end_terminal_activation_request(self):
        logger.info("[RPC] End Terminal Activation Request")
        body, comp, freq, pwr = self._normalize_body()
        logger.debug("[RPC] Activation body=%s", body)
        if not comp or freq is None or pwr is None:
            logger.error("[RPC] Missing parameters for activation")
            return jsonify({"error": "Required parameters missing"}), 400

        conf_log, ok_ops = [], []
        try:
            try:
                act = self._render_json("et_activation_req")
                rid = act["input"]["sdnc-request-header"]["request-id"]
                logger.debug("[RPC] Activation rid=%s", rid)
            except Exception:
                rid = f"act-{int(time.time())}"
                logger.warning("[RPC] No rid in payload, generated=%s", rid)

            if hasattr(self, "pre_activate_A"):
                logger.debug("[RPC] Running pre_activate_A()")
                self.pre_activate_A()
            if hasattr(self, "pre_activate_B"):
                logger.debug("[RPC] Running pre_activate_B()")
                self.pre_activate_B()

            for ip in (self.ipA, self.ipB):
                logger.info("[RPC] Activating end %s", ip)
                res = self.set_power_and_frequency(ip=ip, component_name=comp, frequency=freq, tx_power=pwr)
                ok_ops.append(ip)
                conf_log.append(f"{ip}: power+freq set")

            rA = self.read_target_output_power(ip=self.ipA, component_name=comp)
            rB = self.read_target_output_power(ip=self.ipB, component_name=comp)
            rbA, rbB = rA.get("target_output_power"), rB.get("target_output_power")
            logger.info("[RPC] Activation readback A=%s dBm, Z=%s dBm", rbA, rbB)
            conf_log.append(f"{self.ipA}: {rbA} dBm")
            conf_log.append(f"{self.ipB}: {rbB} dBm")

            return jsonify({
                "output": {
                    "configuration-response-common": {
                        "request-id": rid,
                        "response-code": "success",
                        "response-message": "Request processed successfully!",
                        "ack-final-indicator": "final",
                    }
                },
                "A_end_target_output_power": rbA,
                "Z_end_target_output_power": rbB,
                "End_Terminal_Activation_Status": "Activated",
                "conf_log": conf_log,
                "vendor": self.vendor or "",
            })        
        except Exception as e:
            logger.exception("[RPC] Activation failed: %s", e)
            return jsonify({"error": str(e), "conf_log": conf_log}), 500

    def end_terminal_deactivation_request(self):
        logger.info("[RPC] End Terminal Deactivation Request")
        body, comp, freq, pwr = self._normalize_body()
        logger.debug("[RPC] Deactivation body=%s", body)
        if not comp or freq is None or pwr is None:
            logger.error("[RPC] Missing parameters for deactivation")
            return jsonify({"error": "Required parameters missing"}), 400

        conf_log, ok_ops = [], []
        try:
            try:
                deact = self._render_json("et_deactivation_req")
                rid = deact["input"]["sdnc-request-header"]["request-id"]
                logger.debug("[RPC] Deactivation rid=%s", rid)
            except Exception:
                rid = f"deact-{int(time.time())}"
                logger.warning("[RPC] No rid in payload, generated=%s", rid)

            for ip in (self.ipA, self.ipB):
                logger.info("[RPC] Deactivating end %s", ip)
                res = self.set_power_and_frequency(ip=ip, component_name=comp, frequency=freq, tx_power=pwr)
                ok_ops.append(ip)
                conf_log.append(f"{ip}: power+freq set")

            logger.info("[RPC] Deactivation completed for A and Z")
            return jsonify(
                {
                    "output": {
                        "configuration-response-common": {
                            "request-id": rid,
                            "response-code": "success",
                            "response-message": "Request processed successfully!",
                            "ack-final-indicator": "final",
                        }
                    },
                    "End_Terminal_Activation_Status": "Deactivated",
                    "conf_log": conf_log,
                    "vendor": self.vendor or "",
                }
            )        
        except Exception as e:
            logger.exception("[RPC] Deactivation failed: %s", e)
            return jsonify({"error": str(e), "conf_log": conf_log}), 500


class vendorCController(ConcreteIPSDNCController):
    def __init__(self, config: dict, with_mgr=None):
        logger.info("[Init] vendorCController created")
        super().__init__(config)

    def post_activate_A(self):
        logger.info("[Hook] vendorC post_activate_A")
        self._measurement_on(self.ipA)
    def post_activate_B(self):
        logger.info("[Hook] vendorC post_activate_B")
        self._measurement_on(self.ipB)
    def post_deactivate_A(self):
        logger.info("[Hook] vendorC post_deactivate_A")
        self._measurement_off(self.ipA)
    def post_deactivate_B(self):
        logger.info("[Hook] vendorC post_deactivate_B")
        self._measurement_off(self.ipB)
    def _measurement_on(self, ip: str):
        logger.info("[Hook] Measurement ON at %s", ip)
        xml = self._render_payload("measurement_enable")
        with self._connect(ip) as m:
            m.edit_config(target="running", config=xml); m.commit()
    def _measurement_off(self, ip: str):
        logger.info("[Hook] Measurement OFF at %s", ip)
        xml = self._render_payload("measurement_disable")
        with self._connect(ip) as m:
            m.edit_config(target="running", config=xml); m.commit()


class vendorBController(ConcreteIPSDNCController):
    def __init__(self, config: dict, with_mgr=None):
        logger.info("[Init] vendorBController created")
        super().__init__(config)
        if not (self.jump_host and self.jump_user and self.jump_pass):
            raise RuntimeError("Jump host credentials missing for vendorB")

    def _alloc_port(self) -> int:
        s = socket.socket(); s.bind(("", 0)); port = s.getsockname()[1]; s.close()
        logger.debug("[vendorB] Allocated local port %s for tunnel", port)
        return port

    def _ensure_tunnel(self, dst_host: str, dst_port: int = 830) -> int:
        logger.info("[vendorB] Establishing tunnel to %s:%s via jump %s", dst_host, dst_port, self.jump_host)
        local_port = self._alloc_port()
        cmd = (
            "sshpass -p '{pwd}' ssh "
            "-p {jprt} "
            "-o LogLevel=ERROR "
            "-o StrictHostKeyChecking=no "
            "-o UserKnownHostsFile=/dev/null "
            "-o GlobalKnownHostsFile=/dev/null "
            "-o PreferredAuthentications=password "
            "-o PubkeyAuthentication=no "
            "-o ExitOnForwardFailure=yes "
            "-f -N -L {lp}:{dst}:{dpt} {usr}@{host}"
        ).format(
            pwd=self.jump_pass, jprt=getattr(self, "jump_port", 22), lp=local_port,
            dst=dst_host, dpt=dst_port, usr=self.jump_user, host=self.jump_host
        )

        subprocess.run(cmd, shell=True, check=True)
        time.sleep(1.0)
        # logger.info("[NEC] Tunnel ready on local port %s", local_port)
        return local_port

    def _connect(self, ip: str):
        logger.info("[NEC] Connecting through tunnel to %s", ip)
        lp = self._ensure_tunnel(ip, 830)
        u, p = self._credA if ip == self.ipA else self._credB
        return manager.connect(host="localhost", port=lp, username=u, password=p,
                               hostkey_verify=False, look_for_keys=False, allow_agent=False, timeout=30)
