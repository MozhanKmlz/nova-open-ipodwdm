# routes/ipsdnc_interactions.py
from flask import Blueprint
def create_ipsdnc_bp(ipsdnc_controller):
    bp = Blueprint('ipsdnc_interactions', __name__)

    @bp.route('/end-terminal-performance-info-request', methods=['GET'])
    def performance_info_endpoint():
        return ipsdnc_controller.end_terminal_performance_info_request()

    @bp.route('/end-terminal-activation-request', methods=['POST'])
    def activation_endpoint():
        return ipsdnc_controller.end_terminal_activation_request()

    @bp.route('/end-terminal-deactivation-request', methods=['POST'])
    def deactivation_endpoint():
        return ipsdnc_controller.end_terminal_deactivation_request()

    return bp
