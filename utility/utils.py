import json
import logging
from rich.logging import RichHandler

def get_operational_mode_info():
    try:
        with open('config/operational-mode-info.json', 'r') as file:
            mode_info = json.load(file)
        specific_mode_info = mode_info.get("specific-operational-mode", {})
        return {
            "operational_mode_id": specific_mode_info.get("operational-mode-id"),
            "min_frequency": specific_mode_info.get("min-central-frequency"),
            "max_frequency": specific_mode_info.get("max-central-frequency"),
            "min_granularity": specific_mode_info.get("central-frequency-granularity")
        }

    except Exception as e:
        return {"error": str(e)}

def safe_extract_data(response):
    try:
        if isinstance(response, dict):
            return response
        elif hasattr(response, 'get_json'):
            result = response.get_json()
            if result is None and hasattr(response, 'data'):
                try:
                    result = json.loads(response.data.decode('utf-8'))
                except Exception as inner_e:
                    logging.error(f"Error decoding response.data: {inner_e}")
                    result = None
            return result
        elif hasattr(response, 'data'):
            try:
                return json.loads(response.data.decode('utf-8'))
            except Exception as inner_e:
                logging.error(f"Error decoding response.data: {inner_e}")
                return None
        elif isinstance(response, str):
            return json.loads(response)
        else:
            logging.error(f"Unexpected response type: {type(response)}")
            return None
    except Exception as e:
        logging.error(f"Error extracting data: {e}")
        return None

def setup_logger():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[RichHandler(rich_tracebacks=True)],
        force=True
    )

    logging.getLogger("controllers.base_ipsdnc").setLevel(logging.INFO)
    logging.getLogger("utility.utils").setLevel(logging.DEBUG)
    logging.getLogger("ipsdnc_interactions").setLevel(logging.INFO)
    logging.getLogger("rnc_interactions").setLevel(logging.INFO)
    logging.getLogger("controllers.base_rnc").setLevel(logging.INFO)
    logging.getLogger("orchestrator.nova").setLevel(logging.INFO)

    logging.getLogger("paramiko").setLevel(logging.ERROR)
    logging.getLogger("ncclient").setLevel(logging.ERROR)
    logging.getLogger("ncclient.transport").setLevel(logging.ERROR)      # <— transport layer
    logging.getLogger("ncclient.transport.ssh").setLevel(logging.ERROR)  # <— ssh banner errors
    logging.getLogger("werkzeug").setLevel(logging.ERROR)                # Flask’s HTTP server
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    return logging.getLogger("controllers.base_ipsdnc")
