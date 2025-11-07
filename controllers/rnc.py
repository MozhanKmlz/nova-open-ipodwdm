# controllers/rnc.py
from abc import ABC, abstractmethod

class RNCController(ABC):
    def __init__(self, config):
        """
        config: dict of any parameters you need (e.g. TPCE host/credentials, ports…)
        """
        self.config = config

    @abstractmethod
    def connect_to_tpce(self):
        """Establish SSH tunnel to TPCE and return (ssh_client, local_port, tpce_host)."""
        pass

    @abstractmethod
    def temp_service_create(self):
        """Handle /temp-service-create POST body (dict) -> Flask response data."""
        pass

    @abstractmethod
    def temp_service_list(self):
        """Handle /temp-service-list GET -> Flask response data."""
        pass

    @abstractmethod
    def service_power_setup(self, which: str):
        """Handle service-power-setup (A or B) -> Flask response data."""
        pass

    @abstractmethod
    def service_create(self):
        """Handle /service-create POST -> Flask response data."""
        pass

    @abstractmethod
    def service_list(self):
        """Handle /service-list GET -> Flask response data."""
        pass

    @abstractmethod
    def optical_tunnel_request_cancel(self):
        """Handle /optical-tunnel-request-cancel -> Flask response data."""
        pass

    @abstractmethod
    def service_delete(self):
        """Handle /service-delete POST -> Flask response data."""
        pass
