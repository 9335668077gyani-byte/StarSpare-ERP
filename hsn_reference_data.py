# hsn_reference_data.py
# Built-in HSN Reference Database for Motor Spare Parts Industry
# This module provides a searchable reference of common HSN codes.

# ============================================================
# CATEGORY SHORTCUTS (Quick-assign by business category)
# Each maps to: (hsn_code, description, cgst_rate, sgst_rate)
# ============================================================
HSN_CATEGORIES = {
    "Engine Parts": ("84099900", "Parts of Engines (Other)", 9.0, 9.0),
    "Brake Parts": ("87083000", "Brakes & Servo-Brakes Parts", 9.0, 9.0),
    "Filters (Oil/Air/Fuel)": ("84212300", "Oil or Petrol Filters for IC Engines", 9.0, 9.0),
    "Bearings": ("84821000", "Ball Bearings", 9.0, 9.0),
    "Lubricants & Engine Oil": ("27101990", "Other Lubricating Oils", 9.0, 9.0),
    "Tyres": ("40111000", "New Pneumatic Tyres of Rubber", 9.0, 9.0),
    "Tubes": ("40131000", "Inner Tubes of Rubber", 9.0, 9.0),
    "Batteries": ("85071000", "Lead-Acid Accumulators", 9.0, 9.0),
    "Electrical Parts": ("85122010", "Lighting/Signalling Equipment", 9.0, 9.0),
    "Body Parts / Panels": ("87089900", "Other Motor Vehicle Parts & Accessories", 9.0, 9.0),
    "Clutch Parts": ("87089200", "Silencers & Exhaust Pipes / Clutch Parts", 9.0, 9.0),
    "Suspension Parts": ("87088000", "Suspension Shock Absorbers", 9.0, 9.0),
    "Fasteners & Hardware": ("73181900", "Other Threaded Fasteners of Iron/Steel", 9.0, 9.0),
    "Mirrors & Glass": ("70091000", "Rear-View Mirrors for Vehicles", 9.0, 9.0),
    "Two-Wheeler Parts (General)": ("87141000", "Parts of Motorcycles & Cycles", 9.0, 9.0),
}

# ============================================================
# MASTER REFERENCE DATABASE (~80 common HSN codes)
# ============================================================
HSN_REFERENCE_DB = [
    # --- ENGINE PARTS ---
    {"code": "84099100", "description": "Parts for Spark-Ignition Engines", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84099900", "description": "Parts of Engines (Other)", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84099110", "description": "Piston & Piston Rings", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84099120", "description": "Cylinder Blocks / Cylinder Liners", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84099130", "description": "Valve & Valve Seats", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84099140", "description": "Gaskets & Seals", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84099150", "description": "Connecting Rods", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84091000", "description": "Parts for Aircraft Engines / Crankshaft", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},

    # --- BRAKE PARTS ---
    {"code": "87083000", "description": "Brakes & Servo-Brakes Parts", "cgst": 9.0, "sgst": 9.0, "category": "Brake Parts"},
    {"code": "87083010", "description": "Brake Pads & Brake Shoes", "cgst": 9.0, "sgst": 9.0, "category": "Brake Parts"},
    {"code": "87083020", "description": "Brake Drums & Brake Discs", "cgst": 9.0, "sgst": 9.0, "category": "Brake Parts"},
    {"code": "87083030", "description": "Brake Cables & Brake Levers", "cgst": 9.0, "sgst": 9.0, "category": "Brake Parts"},
    {"code": "87083040", "description": "Master Cylinder / Brake Cylinder", "cgst": 9.0, "sgst": 9.0, "category": "Brake Parts"},

    # --- FILTERS ---
    {"code": "84212300", "description": "Oil or Petrol Filters for IC Engines", "cgst": 9.0, "sgst": 9.0, "category": "Filters (Oil/Air/Fuel)"},
    {"code": "84212100", "description": "Water Filtering Machinery", "cgst": 9.0, "sgst": 9.0, "category": "Filters (Oil/Air/Fuel)"},
    {"code": "84213100", "description": "Air Intake Filters for IC Engines", "cgst": 9.0, "sgst": 9.0, "category": "Filters (Oil/Air/Fuel)"},
    {"code": "84219900", "description": "Filter Parts (Other)", "cgst": 9.0, "sgst": 9.0, "category": "Filters (Oil/Air/Fuel)"},

    # --- BEARINGS ---
    {"code": "84821000", "description": "Ball Bearings", "cgst": 9.0, "sgst": 9.0, "category": "Bearings"},
    {"code": "84822000", "description": "Tapered Roller Bearings", "cgst": 9.0, "sgst": 9.0, "category": "Bearings"},
    {"code": "84823000", "description": "Spherical Roller Bearings", "cgst": 9.0, "sgst": 9.0, "category": "Bearings"},
    {"code": "84824000", "description": "Needle Roller Bearings", "cgst": 9.0, "sgst": 9.0, "category": "Bearings"},
    {"code": "84825000", "description": "Cylindrical Roller Bearings", "cgst": 9.0, "sgst": 9.0, "category": "Bearings"},
    {"code": "84829900", "description": "Bearing Parts (Other)", "cgst": 9.0, "sgst": 9.0, "category": "Bearings"},

    # --- LUBRICANTS & OILS ---
    {"code": "27101990", "description": "Other Lubricating Oils", "cgst": 9.0, "sgst": 9.0, "category": "Lubricants & Engine Oil"},
    {"code": "27101940", "description": "Engine Oil / Motor Oil", "cgst": 9.0, "sgst": 9.0, "category": "Lubricants & Engine Oil"},
    {"code": "27101950", "description": "Gear Oil / Transmission Oil", "cgst": 9.0, "sgst": 9.0, "category": "Lubricants & Engine Oil"},
    {"code": "27101960", "description": "Hydraulic Brake Fluid", "cgst": 9.0, "sgst": 9.0, "category": "Lubricants & Engine Oil"},
    {"code": "27101970", "description": "Cutting Oils / Coolants", "cgst": 9.0, "sgst": 9.0, "category": "Lubricants & Engine Oil"},
    {"code": "34031900", "description": "Greases & Lubricating Preparations", "cgst": 9.0, "sgst": 9.0, "category": "Lubricants & Engine Oil"},

    # --- TYRES & TUBES ---
    {"code": "40111000", "description": "New Pneumatic Tyres - Motor Cars", "cgst": 9.0, "sgst": 9.0, "category": "Tyres"},
    {"code": "40112000", "description": "New Pneumatic Tyres - Buses/Trucks", "cgst": 9.0, "sgst": 9.0, "category": "Tyres"},
    {"code": "40114000", "description": "New Pneumatic Tyres - Motorcycles", "cgst": 9.0, "sgst": 9.0, "category": "Tyres"},
    {"code": "40119000", "description": "New Pneumatic Tyres (Other)", "cgst": 9.0, "sgst": 9.0, "category": "Tyres"},
    {"code": "40131000", "description": "Inner Tubes of Rubber - Motor Cars", "cgst": 9.0, "sgst": 9.0, "category": "Tubes"},
    {"code": "40132000", "description": "Inner Tubes of Rubber - Cycles", "cgst": 9.0, "sgst": 9.0, "category": "Tubes"},

    # --- BATTERIES ---
    {"code": "85071000", "description": "Lead-Acid Accumulators (Batteries)", "cgst": 9.0, "sgst": 9.0, "category": "Batteries"},
    {"code": "85073000", "description": "Nickel-Cadmium Accumulators", "cgst": 9.0, "sgst": 9.0, "category": "Batteries"},
    {"code": "85076000", "description": "Lithium-Ion Accumulators", "cgst": 9.0, "sgst": 9.0, "category": "Batteries"},
    {"code": "85079000", "description": "Battery Parts (Plates, Separators)", "cgst": 9.0, "sgst": 9.0, "category": "Batteries"},

    # --- ELECTRICAL PARTS ---
    {"code": "85122010", "description": "Lighting / Signalling Equipment for Vehicles", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85122020", "description": "Headlamps & Tail Lamps", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85119000", "description": "Ignition / Starting Equipment Parts", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85114000", "description": "Starter Motors for Engines", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85111000", "description": "Spark Plugs", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85113000", "description": "Distributors / Ignition Coils", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85044010", "description": "Voltage Regulators / Rectifiers", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85361000", "description": "Fuses & Fuse Holders", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85443000", "description": "Wiring Harness for Vehicles", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},
    {"code": "85129000", "description": "Horns / Buzzers for Vehicles", "cgst": 9.0, "sgst": 9.0, "category": "Electrical Parts"},

    # --- BODY PARTS & ACCESSORIES ---
    {"code": "87089900", "description": "Other Motor Vehicle Parts & Accessories", "cgst": 9.0, "sgst": 9.0, "category": "Body Parts / Panels"},
    {"code": "87082900", "description": "Body Parts (Other)", "cgst": 9.0, "sgst": 9.0, "category": "Body Parts / Panels"},
    {"code": "87082100", "description": "Safety Seat Belts", "cgst": 9.0, "sgst": 9.0, "category": "Body Parts / Panels"},
    {"code": "87081000", "description": "Bumpers & Parts Thereof", "cgst": 9.0, "sgst": 9.0, "category": "Body Parts / Panels"},

    # --- CLUTCH PARTS ---
    {"code": "87089200", "description": "Silencers/Exhaust Pipes/Clutch Parts", "cgst": 9.0, "sgst": 9.0, "category": "Clutch Parts"},
    {"code": "87089210", "description": "Clutch Plates / Clutch Disc", "cgst": 9.0, "sgst": 9.0, "category": "Clutch Parts"},
    {"code": "87089220", "description": "Clutch Wire / Clutch Cable", "cgst": 9.0, "sgst": 9.0, "category": "Clutch Parts"},

    # --- SUSPENSION ---
    {"code": "87088000", "description": "Suspension Shock Absorbers", "cgst": 9.0, "sgst": 9.0, "category": "Suspension Parts"},
    {"code": "87088010", "description": "Front Fork Assembly", "cgst": 9.0, "sgst": 9.0, "category": "Suspension Parts"},
    {"code": "73202000", "description": "Helical Springs (Suspension)", "cgst": 9.0, "sgst": 9.0, "category": "Suspension Parts"},

    # --- FASTENERS & HARDWARE ---
    {"code": "73181900", "description": "Other Threaded Fasteners (Iron/Steel)", "cgst": 9.0, "sgst": 9.0, "category": "Fasteners & Hardware"},
    {"code": "73181500", "description": "Bolts & Screws (Iron/Steel)", "cgst": 9.0, "sgst": 9.0, "category": "Fasteners & Hardware"},
    {"code": "73181600", "description": "Nuts (Iron/Steel)", "cgst": 9.0, "sgst": 9.0, "category": "Fasteners & Hardware"},
    {"code": "73182900", "description": "Non-Threaded Fasteners (Washers, Clips)", "cgst": 9.0, "sgst": 9.0, "category": "Fasteners & Hardware"},

    # --- MIRRORS & GLASS ---
    {"code": "70091000", "description": "Rear-View Mirrors for Vehicles", "cgst": 9.0, "sgst": 9.0, "category": "Mirrors & Glass"},
    {"code": "70071100", "description": "Toughened Safety Glass (Windshield)", "cgst": 9.0, "sgst": 9.0, "category": "Mirrors & Glass"},

    # --- TWO-WHEELER PARTS ---
    {"code": "87141000", "description": "Parts of Motorcycles & Cycles", "cgst": 9.0, "sgst": 9.0, "category": "Two-Wheeler Parts (General)"},
    {"code": "87141010", "description": "Handlebar / Grips / Levers", "cgst": 9.0, "sgst": 9.0, "category": "Two-Wheeler Parts (General)"},
    {"code": "87141020", "description": "Kick Starter / Side Stand", "cgst": 9.0, "sgst": 9.0, "category": "Two-Wheeler Parts (General)"},
    {"code": "87141030", "description": "Speedometer Cable / Speedo Gear", "cgst": 9.0, "sgst": 9.0, "category": "Two-Wheeler Parts (General)"},
    {"code": "87141040", "description": "Chain & Sprocket Kit", "cgst": 9.0, "sgst": 9.0, "category": "Two-Wheeler Parts (General)"},
    {"code": "87149200", "description": "Wheel Rims & Spokes", "cgst": 9.0, "sgst": 9.0, "category": "Two-Wheeler Parts (General)"},
    {"code": "87149500", "description": "Saddles / Seats for Cycles", "cgst": 9.0, "sgst": 9.0, "category": "Two-Wheeler Parts (General)"},

    # --- CHAINS, BELTS, GEARS ---
    {"code": "73158900", "description": "Chain (Other - Transmission)", "cgst": 9.0, "sgst": 9.0, "category": "Two-Wheeler Parts (General)"},
    {"code": "40103900", "description": "Transmission Belts (V-Belts)", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84839000", "description": "Gears / Gear Boxes Parts", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},

    # --- MISCELLANEOUS ---
    {"code": "40169300", "description": "O-Rings / Rubber Gaskets", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84814000", "description": "Safety / Relief Valves", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84133000", "description": "Fuel / Oil / Coolant Pumps", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
    {"code": "84859000", "description": "Machinery Parts (General)", "cgst": 9.0, "sgst": 9.0, "category": "Engine Parts"},
]

def auto_assign_hsn(part_name):
    """
    Intelligently auto-assigns an HSN and GST rate based on a part's name.
    Useful for completely new parts imported from vendor catalogs that lack DB entries.
    Returns: (hsn_code, gst_rate)
    """
    part_name_lower = str(part_name).lower()
    hsn = '87089900' # Default fallback
    gst_rate = 18.0
    
    try:
        words = [w for w in part_name_lower.replace('-', ' ').split() if len(w) > 3]
        best_match = None
        for ref in HSN_REFERENCE_DB:
            ref_desc = ref['description'].lower()
            if part_name_lower in ref_desc or any(w in ref_desc for w in words):
                best_match = ref
                break
                
        if not best_match:
            if 'oil' in part_name_lower or 'lubricant' in part_name_lower:
                hsn, gst_rate = '27101990', 18.0
            elif 'filter' in part_name_lower:
                hsn, gst_rate = '84212300', 18.0
            elif 'brake' in part_name_lower:
                hsn, gst_rate = '87083000', 18.0
            elif 'bearing' in part_name_lower:
                hsn, gst_rate = '84821000', 18.0
            elif 'bike' in part_name_lower or 'two wheeler' in part_name_lower:
                hsn, gst_rate = '87141000', 18.0
            elif 'car' in part_name_lower or 'four wheeler' in part_name_lower:
                hsn, gst_rate = '87089900', 18.0
            elif any(k in part_name_lower for k in ['cover', 'frame', 'panel', 'guard', 'body', 'handle']):
                hsn, gst_rate = '87089900', 18.0
            elif any(k in part_name_lower for k in ['relay', 'switch', 'cable', 'wire', 'sensor', 'bulb']):
                hsn, gst_rate = '85129000', 18.0
        else:
            hsn = best_match['code']
            gst_rate = best_match['cgst'] + best_match['sgst']
    except Exception as e:
        import logging
        logging.warning(f"Failed to auto-assign HSN for {part_name}: {e}")
        
    return hsn, gst_rate
