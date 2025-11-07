from flask import Blueprint, request

def create_rnc_bp(rnc_controller):
    bp = Blueprint('rnc_interactions', __name__)

    @bp.route('/temp-service-create', methods=['POST'])
    def temp_service_create():
        return rnc_controller.temp_service_create(request.get_json())

    @bp.route('/temp-service-list', methods=['GET'])
    def temp_service_list():
        return rnc_controller.temp_service_list()

    @bp.route('/service-power-setup', methods=['POST'])
    def service_power_setup_A():
        data = request.get_json()
        return rnc_controller.service_power_setup(data, which='A')

    @bp.route('/service-power-setup-b', methods=['POST'])
    def service_power_setup_B():
        data = request.get_json()
        return rnc_controller.service_power_setup(data, which='B')

    @bp.route('/service-create', methods=['POST'])
    def service_create():
        return rnc_controller.service_create(request.get_json())

    @bp.route('/service-list', methods=['GET'])
    def service_list():
        return rnc_controller.service_list(request.get_json() or {})

    @bp.route('/optical-tunnel-request-cancel', methods=['POST'])
    def optical_tunnel_request_cancel():
        return rnc_controller.optical_tunnel_request_cancel(request.get_json() or {})

    @bp.route('/service-delete', methods=['POST'])
    def service_delete():
        return rnc_controller.service_delete(request.get_json() or {})

    return bp
