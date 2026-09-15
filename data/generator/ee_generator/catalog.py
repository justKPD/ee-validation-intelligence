"""Fictional catalog of E/E components, variants and vocabulary."""

from __future__ import annotations

# (short name, domain, asil)
COMPONENTS: list[tuple[str, str, str]] = [
    ("BCM", "body", "B"),
    ("BMS", "hv_powertrain", "D"),
    ("VCU", "hv_powertrain", "D"),
    ("ADAS_GATEWAY", "adas", "C"),
    ("INFOTAINMENT", "infotainment", "QM"),
    ("DCDC", "hv_powertrain", "C"),
    ("OBC", "hv_powertrain", "B"),
    ("HVAC_ECU", "body", "QM"),
    ("EPS", "chassis", "D"),
    ("ABS_ESC", "chassis", "D"),
    ("AIRBAG", "chassis", "D"),
    ("TCU", "connectivity", "QM"),
    ("INV_FRONT", "hv_powertrain", "D"),
    ("INV_REAR", "hv_powertrain", "D"),
    ("HV_JUNCTION", "hv_powertrain", "C"),
    ("THERMAL_MGMT", "hv_powertrain", "B"),
    ("CHARGE_PORT_CTRL", "hv_powertrain", "B"),
    ("SEAT_CTRL", "body", "QM"),
    ("DOOR_CTRL_FL", "body", "A"),
    ("DOOR_CTRL_FR", "body", "A"),
    ("LIGHT_CTRL", "body", "B"),
    ("WIPER_CTRL", "body", "A"),
    ("KEYLESS_ENTRY", "body", "A"),
    ("INSTRUMENT_CLUSTER", "infotainment", "B"),
    ("HUD", "infotainment", "A"),
    ("AUDIO_AMP", "infotainment", "QM"),
    ("CENTRAL_GATEWAY", "connectivity", "C"),
    ("RADAR_FRONT", "adas", "C"),
    ("CAMERA_FRONT", "adas", "C"),
    ("LIDAR_CTRL", "adas", "C"),
    ("PARK_ASSIST", "adas", "B"),
    ("SURROUND_VIEW", "adas", "A"),
    ("TPMS", "chassis", "A"),
    ("EPB", "chassis", "C"),
    ("SUSPENSION_CTRL", "chassis", "B"),
    ("STEERING_ANGLE", "chassis", "D"),
    ("OTA_MANAGER", "connectivity", "B"),
    ("V2X_UNIT", "connectivity", "A"),
    ("DIAG_MASTER", "connectivity", "QM"),
    ("POWER_DIST", "body", "C"),
]

SUPPLIERS = [
    "Fictional Supplier Alpha",
    "Fictional Supplier Beta",
    "Fictional Supplier Gamma",
    "In-house (fictional)",
]

VARIANTS = [
    ("V1", "Fictional BEV Sedan EU", "BEV", "EU", "hv,adas_l2,heat_pump"),
    ("V2", "Fictional PHEV SUV US", "PHEV", "US", "hv,adas_l2,tow"),
    ("V3", "Fictional BEV Performance", "BEV", "EU", "hv,adas_l2_plus,air_suspension,hud"),
    ("V4", "Fictional ICE Compact CN", "ICE", "CN", "adas_l1"),
]

# domains not applicable to ICE variant
HV_DOMAIN = "hv_powertrain"

REQ_CATEGORIES = ["functional", "safety", "diagnostic", "communication", "performance", "cybersecurity"]

REQ_TEMPLATES = {
    "functional": "{c} shall provide {x} within specified operating range",
    "safety": "{c} shall enter safe state on {x} fault within FTTI",
    "diagnostic": "{c} shall report DTC for {x} plausibility failure",
    "communication": "{c} shall transmit {x} signal with cycle time tolerance",
    "performance": "{c} shall complete {x} within latency budget",
    "cybersecurity": "{c} shall reject unauthenticated {x} requests",
}

SIGNALS = [
    "voltage",
    "current",
    "temperature",
    "wake-up",
    "CAN timeout",
    "torque request",
    "speed",
    "state-of-charge",
    "brake pressure",
    "steering torque",
    "door status",
    "light command",
    "object list",
    "firmware image",
    "diagnostic session",
]

FAMILY_BY_DOMAIN = {
    "hv_powertrain": ["hv_safety", "energy_mgmt", "charging"],
    "chassis": ["dynamics", "functional_safety"],
    "body": ["body_functions", "network_mgmt"],
    "adas": ["perception", "adas_functions"],
    "infotainment": ["hmi", "media"],
    "connectivity": ["ota", "diagnostics", "network_mgmt"],
}

FAILURE_STAGES = ["startup", "steady_state", "transition", "shutdown", "fault_injection", "wake_sleep"]
