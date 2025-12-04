from flask import Blueprint, request

def create_rnc_bp(rnc_controller):
    bp = Blueprint('rnc_interactions', __name__)

    @bp.route('/temp-service-create', methods=['POST'])
    def temp_service_create():
        try:
            return rnc_controller.temp_service_create(request.get_json())
        except Exception as e:
            return rnc_controller._err(str(e), 400)

    @bp.route('/temp-service-list', methods=['GET'])
    def temp_service_list():
        try:
            return rnc_controller.temp_service_list()
        except Exception as e:
            return rnc_controller._err(str(e), 400)

    @bp.route('/service-power-setup', methods=['POST'])
    def service_power_setup_A():
        data = request.get_json()
        try:
            return rnc_controller.service_power_setup(data, which='A')
        except Exception as e:
            return rnc_controller._err(str(e), 400)

    @bp.route('/service-power-setup-b', methods=['POST'])
    def service_power_setup_B():
        data = request.get_json()
        try:
            return rnc_controller.service_power_setup(data, which='B')
        except Exception as e:
            return rnc_controller._err(str(e), 400)

    @bp.route('/service-create', methods=['POST'])
    def service_create():
        try:
            return rnc_controller.service_create(request.get_json())
        except Exception as e:
            return rnc_controller._err(str(e), 400)

    @bp.route('/service-list', methods=['GET'])
    def service_list():
        try:
            return rnc_controller.service_list(request.get_json() or {})
        except Exception as e:
            return rnc_controller._err(str(e), 400)

    @bp.route('/optical-tunnel-request-cancel', methods=['POST'])
    def optical_tunnel_request_cancel():
        try:
            return rnc_controller.optical_tunnel_request_cancel(request.get_json() or {})
        except Exception as e:
            return rnc_controller._err(str(e), 400)

    @bp.route('/service-delete', methods=['POST'])
    def service_delete():
        try:
            return rnc_controller.service_delete(request.get_json() or {})
        except Exception as e:
            return rnc_controller._err(str(e), 400)

    return bp
