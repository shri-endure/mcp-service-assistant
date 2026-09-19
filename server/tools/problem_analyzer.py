"""Problem Analyzer Tool for MCP Service Resolution Assistant.

Analyzes customer problem descriptions using keyword and semantic matching to determine:
- Service category (AC Repair, Laptop Repair, Plumbing, Washing Machine Repair)
- Detected issue summary
- Common causes
- Safe DIY checks
- Confidence score
"""

import os
import re
import sys
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def analyze_problem(problem: str) -> Dict[str, Any]:
    """Analyze the user's issue and return category, issue summary, and confidence.

    Supported Categories:
    - AC Repair
    - Laptop Repair
    - Plumbing
    - Washing Machine Repair

    For unsupported problems, returns category 'Unknown', issue 'detected problem',
    confidence 0, and user-friendly message.
    """
    if not problem or not isinstance(problem, str):
        return {
            "category": "Unknown",
            "issue": "detected problem",
            "confidence": 0,
            "message": "Sorry, this service category isn't currently supported.",
        }

    text = problem.lower()

    # 1. Washing Machine Repair
    if "washing machine" in text or "washer" in text:
        if "spin" in text:
            issue = "washing machine not spinning"
            causes = [
                "Unbalanced or overloaded laundry distribution inside the drum",
                "Worn or broken drive belt or motor coupling",
                "Defective lid switch or door lock sensor preventing high-speed spin cycle",
            ]
            manual_checks = [
                "Redistribute clothes evenly inside the drum and try a spin-only cycle",
                "Ensure the door/lid clicks firmly shut and locks securely",
                "Rotate the drum manually by hand when powered off to check for mechanical resistance",
            ]
        elif "drain" in text:
            issue = "washing machine not draining"
            causes = [
                "Clogged drain pump filter or coin trap (lint, coins, small debris)",
                "Kinked, twisted, or blocked drainage hose at the back",
                "Failed drain pump motor or jammed impeller",
            ]
            manual_checks = [
                "Open the coin trap/filter cap at the bottom front, drain residual water, and rinse the filter",
                "Inspect the rear drain pipe to ensure it is not pinched, bent, or positioned too high",
                "Run a standalone 'Drain' cycle to listen if the drain pump motor is humming or silent",
            ]
        elif "leak" in text:
            issue = "washing machine leaking"
            causes = [
                "Loose water inlet hose connection or worn rubber washer",
                "Cracked drain hose or detergent drawer overflow blockage",
                "Worn front door rubber bellows gasket (front-load models)",
            ]
            manual_checks = [
                "Check the hot and cold water inlet connections behind the washer for moisture",
                "Pull out the detergent dispensing tray and clean out hardened soap buildup",
                "Inspect the circular door rubber seal for tears or trapped foreign objects",
            ]
        elif any(k in text for k in ["noise", "noisy", "vibrat", "shak"]):
            issue = "washing machine excessive vibration/noise"
            causes = [
                "Unlevel machine footing on floor",
                "Worn drum shock absorbers or suspension springs",
                "Foreign coin or hairclip caught between inner and outer tub",
            ]
            manual_checks = [
                "Press down on diagonal corners of the machine to check for rocking; adjust leveling feet",
                "Verify transit bolts were completely removed (if newly installed)",
                "Spin the drum by hand to listen for scraping coins or metal clips",
            ]
        else:
            issue = "washing machine breakdown"
            causes = [
                "Electrical power supply or control board PCB fault",
                "Water pressure inlet valve failure",
                "Door latch mechanism failure",
            ]
            manual_checks = [
                "Verify the power plug is secure in a working high-amp socket",
                "Check water taps connected to the washer are fully turned on",
                "Power cycle the machine: unplug for 5 minutes, reconnect, and try running a rinse cycle",
            ]

        return {
            "category": "Washing Machine Repair",
            "issue": issue,
            "confidence": 0.95,
            "causes": causes,
            "manual_checks": manual_checks,
        }

    # 2. Laptop Repair
    if any(
        k in text
        for k in [
            "laptop",
            "notebook",
            "macbook",
            "computer",
            "pc",
            "personel computer",
            "personal computer",
        ]
    ):
        if any(k in text for k in ["overheat", "heating", "hot"]):
            issue = "Laptop overheating"
            causes = [
                "Heavy dust accumulation blocking the cooling fan and heat sink vents",
                "Dried out or degraded thermal paste between CPU/GPU and heat sink",
                "Background processes or malware consuming excessive CPU/GPU resources",
            ]
            manual_checks = [
                "Use the laptop on a flat, rigid desk surface (never on a bed or pillow) to ensure open airflow",
                "Use a soft brush or compressed air to gently clear dust from the exhaust side vents",
                "Open Task Manager (Ctrl+Shift+Esc) to inspect and close programs with high CPU/memory usage",
            ]
        elif any(k in text for k in ["battery", "charge", "charging"]):
            issue = "Laptop battery issue"
            causes = [
                "Degraded lithium-ion battery cells past their lifespan",
                "Faulty power adapter charger brick, damaged cable, or loose DC jack",
                "Corrupted battery management driver or BIOS firmware glitch",
            ]
            manual_checks = [
                "Try plugging the charger into a different wall outlet directly without surge protector",
                "Inspect the charging pin and port for bent pins, dust, or wobbling",
                "Perform a battery reset: power off, disconnect charger, hold power button for 30s, reconnect",
            ]
        elif any(k in text for k in ["screen", "display"]):
            issue = "Laptop display issue"
            causes = [
                "Loose or damaged internal eDP display ribbon cable",
                "Defective LCD backlight or cracked display matrix",
                "Corrupted graphics driver or system hibernation glitch",
            ]
            manual_checks = [
                "Connect the laptop to an external TV or monitor via HDMI to verify if graphics card works",
                "Press Windows Key + Ctrl + Shift + B to restart the graphics driver",
                "Shine a flashlight closely at the screen to check if faint image is visible (backlight test)",
            ]
        elif any(k in text for k in ["slow", "freeze", "freezing", "lag"]):
            issue = "Laptop performance issue"
            causes = [
                "Storage drive (HDD/SSD) nearly 100% full or failing health",
                "Too many background startup applications consuming RAM",
                "Thermal throttling due to high operating temperature",
            ]
            manual_checks = [
                "Free up disk space on drive C: ensuring at least 20 GB free",
                "Disable unnecessary startup apps via Task Manager > Startup tab",
                "Run Windows Disk Cleanup and check for pending OS updates",
            ]
        elif any(k in text for k in ["turn on", "power", "boot"]):
            issue = "Laptop not turning on"
            causes = [
                "Completely drained battery or non-functional power adapter",
                "Static charge buildup on motherboard circuitry",
                "Short circuit in charging circuitry or power button failure",
            ]
            manual_checks = [
                "Disconnect all external USB devices, printers, and SD cards",
                "Perform an EC hard reset: hold the power button down continuously for 30-40 seconds",
                "Leave the laptop plugged into charger for 30 minutes before trying to turn on",
            ]
        else:
            issue = "Laptop issue"
            causes = [
                "Software/driver corruption",
                "Hardware component degradation",
                "Overheating or power delivery instability",
            ]
            manual_checks = [
                "Restart the laptop and check for driver updates",
                "Run built-in hardware diagnostics (F12 or Esc during startup)",
                "Ensure vents are clear and charger is supplying stable power",
            ]

        return {
            "category": "Laptop Repair",
            "issue": issue,
            "confidence": 0.95,
            "causes": causes,
            "manual_checks": manual_checks,
        }

    # 3. AC Repair
    if bool(re.search(r"\bac\b", text)) or any(
        k in text for k in ["air conditioner", "air conditioning", "cooling", "hvac"]
    ):
        if any(k in text for k in ["cooling", "cool", "cold", "warm air"]):
            issue = "AC not cooling"
            causes = [
                "Severely clogged or dusty indoor air filter restricting airflow across the cooling coils",
                "Low refrigerant (Freon gas) level caused by a copper pipe micro-leak",
                "Dirty outdoor condenser coils or failing outdoor compressor run capacitor",
                "Thermostat improperly configured or faulty temperature sensor",
            ]
            manual_checks = [
                "Check remote: ensure mode is set to 'Cool' (❄️) with temperature set between 22°C–24°C, not 'Fan' or 'Dry' mode",
                "Open the indoor unit front panel, slide out the mesh air filters, rinse under water, dry and reinstall",
                "Check outdoor unit: ensure at least 2 feet of clear space around it with no leaves or blockage",
                "Check your home MCB electrical panel to ensure the dedicated AC compressor breaker hasn't tripped",
            ]
        elif any(k in text for k in ["leak", "water"]):
            issue = "AC water leakage"
            causes = [
                "Blocked or choked condensate drain pipe due to algae, fungus, or dust sludge",
                "Frozen indoor evaporator coils melting rapidly due to restricted airflow",
                "Improper or unlevel indoor unit mounting causing drain pan overflow",
            ]
            manual_checks = [
                "Inspect the outdoor drain hose exit point for water flow or visible dirt clog",
                "Power off the unit and check if indoor cooling fins have thick frost or ice buildup",
                "Ensure the indoor unit is mounted horizontally and not tilting away from the drain pipe",
            ]
        elif any(k in text for k in ["noise", "sound"]):
            issue = "AC unusual noise"
            causes = [
                "Loose blower wheel fan or unlubricated fan motor bearings",
                "Debris or loose foreign objects caught in the outdoor unit fan blade",
                "Refrigerant piping vibration against wall or loose casing screws",
            ]
            manual_checks = [
                "Power off AC and inspect outdoor unit fan through the protective grill for stuck twigs/leaves",
                "Ensure the indoor front casing is snapped tightly shut",
                "Check if rubber anti-vibration pads under outdoor unit mounting brackets are worn out",
            ]
        elif any(k in text for k in ["turn on", "power", "start"]):
            issue = "AC not powering on"
            causes = [
                "Tripped MCB circuit breaker or blown stabilizer fuse",
                "Exhausted remote control batteries or faulty remote IR transmitter",
                "Defective main control PCB board or wiring connection",
            ]
            manual_checks = [
                "Replace remote batteries with fresh AAA cells and test pointing at phone camera to check IR flash",
                "Check the manual emergency power button behind the indoor unit front panel",
                "Verify stabilizer output indicator lamp is glowing green with normal voltage",
            ]
        elif any(k in text for k in ["smell", "odor"]):
            issue = "AC bad odor"
            causes = [
                "Mold, mildew, or bacterial growth in the wet condensate drain tray",
                "Stale dirt buildup on the evaporator fins",
                "Animal or insect trapped in ductwork or outdoor section",
            ]
            manual_checks = [
                "Wash the mesh filters and allow them to dry completely in sunlight",
                "Run the AC on 'Fan' mode for 45 minutes to dry out internal moisture",
                "Clean the indoor unit louvers and accessible parts with a mild disinfectant wipe",
            ]
        else:
            issue = "AC not cooling"
            causes = [
                "Clogged air filter restricting airflow",
                "Refrigerant gas leakage or dirty condenser coil",
                "Thermostat sensor miscalibration",
            ]
            manual_checks = [
                "Verify remote mode is set to 'Cool' mode (❄️) below room temperature",
                "Wash and clean the indoor mesh air filters",
                "Ensure outdoor unit has unobstructed airflow",
            ]

        return {
            "category": "AC Repair",
            "issue": issue,
            "confidence": 0.95,
            "causes": causes,
            "manual_checks": manual_checks,
        }

    # 4. Plumbing
    if any(
        k in text
        for k in [
            "pipe",
            "pipes",
            "plumbing",
            "plumber",
            "tap",
            "faucet",
            "drain",
            "drainage",
            "sink",
            "toilet",
            "bathroom",
            "shower",
            "flush",
            "washroom",
            "sewer",
        ]
    ) or ("water" in text and "leak" in text):
        if any(k in text for k in ["leak", "leaking", "leakage"]):
            issue = "water leakage"
            causes = [
                "Worn rubber washer, O-ring, or degraded ceramic cartridge in faucet",
                "Corroded or loose pipe joint fitting under the sink",
                "High municipal water pressure causing pipe joint displacement",
            ]
            manual_checks = [
                "Shut off the local angle stop valve located underneath the sink or behind the fixture",
                "Hand-tighten any loose slip-nut pipe connections beneath the basin",
                "Wipe pipe dry and wrap temporary waterproof silicone tape around the dripping point until technician arrives",
            ]
        elif any(k in text for k in ["clog", "clogged", "block", "blocked"]):
            issue = "clogged drain"
            causes = [
                "Soap scum, hair, and grease accumulation in the P-trap curved pipe",
                "Food scraps or oil solidifying in the kitchen sink waste pipe",
                "Foreign sanitary items lodged in toilet outlet",
            ]
            manual_checks = [
                "Remove hair or debris from the surface drain strainer using a small hook or glove",
                "Pour 1 cup of baking soda followed by 1 cup of white vinegar down the drain, let sit 20 minutes, then flush with hot water",
                "Use a standard cup plunger with a firm downward seal over the drain opening to loosen blockage",
            ]
        elif any(k in text for k in ["tap", "faucet"]):
            issue = "dripping faucet"
            causes = [
                "Worn internal rubber seat washer or damaged ceramic disc cartridge",
                "Sediment and mineral scale buildup inside the aerator spout",
            ]
            manual_checks = [
                "Unscrew the aerator tip from the faucet mouth and rinse out trapped sand or mineral grit",
                "Turn the faucet handle firmly to check if the drip slows, taking care not to crack the valve",
                "Locate and close the shut-off valve under the basin to stop continuous water loss",
            ]
        elif "toilet" in text:
            issue = "toilet issue"
            causes = [
                "Worn flush flapper seal allowing water to run continuously into bowl",
                "Misadjusted float ball valve causing cistern overflow",
                "Partial obstruction in the toilet S-trap or wax ring seal leak",
            ]
            manual_checks = [
                "Remove the cistern tank lid and check if the chain is tangled or flapper valve is properly seating",
                "Adjust the float valve arm to set the water level 1 inch below the overflow pipe",
                "Use a toilet plunger with a flange to clear sluggish flush drainage",
            ]
        else:
            issue = "water leakage"
            causes = [
                "Loose pipe joint connection or worn gasket",
                "Debris or hair accumulation causing slow drainage",
            ]
            manual_checks = [
                "Turn off the local water isolation valve to prevent flooding",
                "Check under-sink fittings for loose slip nuts",
                "Clear surface drain traps of hair and soap residue",
            ]

        return {
            "category": "Plumbing",
            "issue": issue,
            "confidence": 0.95,
            "causes": causes,
            "manual_checks": manual_checks,
        }

    # Unsupported problems (STEP 26: Invalid service category)
    return {
        "category": "Unknown",
        "issue": "detected problem",
        "confidence": 0,
        "message": "Sorry, this service category isn't currently supported.",
    }
