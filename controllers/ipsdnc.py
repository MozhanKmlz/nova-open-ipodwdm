from abc import ABC, abstractmethod


class IPSDNCController(ABC):
    """
    OpenConfig-only abstract controller with hook methods for vendor-specific
    pre/post steps and required OpenConfig operations.
    """

    def __init__(self, config: dict):
        self.config = config
        self.vendor = config.get("vendor", "").lower()

        # Common addressing / config keys expected
        self.ipA = config["routera_ip"]
        self.ipB = config["routerb_ip"]


    # --------- Required OpenConfig operations to be implemented by vendors ---------
    @abstractmethod
    def set_power_and_frequency(self, *, ip: str, component_name: str, frequency, tx_power) -> dict:
        """
        Must send OpenConfig edit-config with <frequency> and <target-output-power>.
        Returns dict like {"message": "..."} or {"error": "..."}.
        """
        raise NotImplementedError

    @abstractmethod
    def read_target_output_power(self, *, ip: str, component_name: str) -> dict:
        """
        Must return {"target_output_power": float} or {"error": "..."}.
        """
        raise NotImplementedError

    # --------- RPCs (public endpoints) to be provided (or by a shared base) ---------
    @abstractmethod
    def end_terminal_performance_info_request(self):
        raise NotImplementedError

    @abstractmethod
    def end_terminal_activation_request(self):
        raise NotImplementedError

    @abstractmethod
    def end_terminal_deactivation_request(self):
        raise NotImplementedError
