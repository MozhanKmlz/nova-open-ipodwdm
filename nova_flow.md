# NOVA Service Orchestration Flow

```mermaid
%%{init: {"theme": "base", "themeVariables": {
    "actorBkg": "#E8F0FE",
    "actorBorder": "#1A73E8",
    "actorTextColor": "#000000",
    "primaryColor": "#A7C7E7",
    "primaryBorderColor": "#1A73E8",
    "primaryTextColor": "#000000",
    "lineColor": "#1A73E8",
    "signalColor": "#1A73E8",
    "fontSize": "14px",
    "noteBkgColor": "#FFFBEA",
    "noteBorderColor": "#F4B400"
}}}%%

sequenceDiagram
    autonumber
    participant client as "Client"
    participant nova as "NOVA"
    participant vendor as "VendorDispatch"
    participant etc as "End Terminal Controller"
    participant mongo as "MongoDB"
    participant rnc as "ROADM Network Controller Handler"
    participant tpce as "TransportPCE"
    participant kafka as "Kafka"

    note over etc: Uses OpenConfig Lookup Engine<br/>Maps revision → version → tag<br/>Reads local openconfig-public repo

    client->>nova: POST /create-service
    nova->>vendor: Select vendor controller
    vendor->>etc: Instantiate (Anritsu / NEC / Base)

    %% Step 1 - End Terminal Performance Info
    nova->>etc: end_terminal_performance_info_request()
    etc->>mongo: Fetch et_performance_info_req
    etc->>Devices: NETCONF get-config (capabilities)
    etc-->>nova: Performance info JSON

    %% Step 2 - Temporary Service Creation
    nova->>rnc: temp_service_create()
    rnc->>mongo: Fetch IC_SRG1_PP1.temp_service_create
    rnc->>tpce: RESTCONF temp-service-create
    tpce-->>kafka: Publish "Path Computation Completed"
    kafka-->>nova: Receive path computation result

    %% Step 3 - End Terminal Activation
    nova->>etc: end_terminal_activation_request()
    etc->>mongo: Fetch et_activation_req
    etc->>Devices: NETCONF edit-config (set power/frequency)
    etc->>Devices: NETCONF get-config (read_target_output_power A)
    etc->>Devices: NETCONF get-config (read_target_output_power Z)
    etc-->>nova: Activation result JSON (with readback values)

    %% Step 4 - Service Creation
    nova->>rnc: service_create()
    rnc->>mongo: Fetch IC_SRG1_PP1.service_create
    rnc->>tpce: RESTCONF service-create
    tpce-->>kafka: Publish "Service Provisioned Successfully"
    kafka-->>nova: Receive service provisioning status

    %% Step 5 - Power Control
    nova->>rnc: service_power_setup(A)
    rnc->>mongo: Fetch IC_SRG1_PP1.end_terminal_power_control_A
    rnc->>tpce: RESTCONF service-power-setup (A-end)
    nova->>rnc: service_power_setup(B)
    rnc->>mongo: Fetch IC_SRG1_PP1.end_terminal_power_control_B
    rnc->>tpce: RESTCONF service-power-setup (Z-end)

    %% Step 6 - Completion
    nova-->>client: Final service response JSON
