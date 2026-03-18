"""
BlindNav - Walking navigation assistant for blind users.
Fixed destination: Painavu, Idukki District, Kerala (9.8453, 76.9730)
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import traceback
import logging
from math import radians, sin, cos, atan2, sqrt

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
logging.basicConfig(level=logging.DEBUG)
log = app.logger

# Add error handlers
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api'):
        return jsonify({"success": False, "error": "API endpoint not found"}), 404
    return "Page not found", 404

@app.errorhandler(500)
def internal_error(error):
    log.error(f"Internal server error: {error}")
    if request.path.startswith('/api'):
        return jsonify({"success": False, "error": "Internal server error"}), 500
    return "Internal server error", 500

# ── FIXED DESTINATION ─────────────────────────────────────────────────
PAINAVU_LAT  = 9.8465
PAINAVU_LNG  = 76.9469
PAINAVU_NAME = "Painavu, Idukki District, Kerala"

# ── CONFIG ────────────────────────────────────────────────────────────
STEP_LENGTH  = 0.65
OSRM_BASE    = "https://router.project-osrm.org"
NOMINATIM    = "https://nominatim.openstreetmap.org"
ORS_BASE     = "https://api.openrouteservice.org/v2"
ORS_API_KEY  = "5b3ce3597851110001cf6248"  # Free public API key (register for your own)
HEADERS      = {
    "User-Agent": "BlindNav/1.0 (accessibility-project; contact@blindnav.org)",
    "Accept": "application/json"
}
TIMEOUT      = 20

# ── HELPERS ───────────────────────────────────────────────────────────

def steps(meters):
    return max(1, round(meters / STEP_LENGTH))

def steps_text(meters):
    s = steps(meters)
    if s <= 3:
        return "a few steps"
    rounded = round(s / 5) * 5 or 5
    return f"about {rounded} steps"

def metres_text(m):
    if m < 100:
        return f"{round(m)} metres"
    elif m < 1000:
        return f"{round(m / 10) * 10} metres"
    else:
        return f"{round(m / 1000, 1)} kilometres"

def cardinal(bearing):
    dirs = ["north", "north-east", "east", "south-east",
            "south", "south-west", "west", "north-west"]
    return dirs[round(bearing / 45) % 8]

def maneuver_to_blind_friendly(mtype, modifier, bearing):
    """Convert maneuver type and modifier to blind-friendly direction words.
    Uses forward/left/right/back (with slight/sharp variants) instead of compass directions."""
    if modifier == "straightahead":
        return "forward"
    elif "sharp" in modifier and "left" in modifier:
        return "sharply left"
    elif "sharp" in modifier and "right" in modifier:
        return "sharply right"
    elif "slight" in modifier and "left" in modifier:
        return "slightly left"
    elif "slight" in modifier and "right" in modifier:
        return "slightly right"
    elif "left" in modifier:
        return "left"
    elif "right" in modifier:
        return "right"
    elif "uturn" in modifier:
        return "back"
    else:
        return "forward"

def build_reminder(mtype, modifier, distance):
    """Generate a pre-turn reminder for approximately 5 steps before the turn.
    Fires when approximately 10-15m from the maneuver point."""
    if mtype not in ("turn", "fork", "new name", "merge"):
        return None
    
    # Build the direction phrase
    direction = maneuver_to_blind_friendly(mtype, modifier, 0)
    
    if mtype == "fork":
        if "left" in modifier:
            return "Reminder. In about 5 steps, keep left at the fork."
        elif "right" in modifier:
            return "Reminder. In about 5 steps, keep right at the fork."
        else:
            return "Reminder. In about 5 steps, continue at the fork."
    elif mtype == "merge":
        if "left" in modifier:
            return "Reminder. In about 5 steps, merge left."
        elif "right" in modifier:
            return "Reminder. In about 5 steps, merge right."
        else:
            return "Reminder. In about 5 steps, merge ahead."
    elif mtype == "new name":
        if "left" in modifier:
            return "Reminder. In about 5 steps, bear left."
        elif "right" in modifier:
            return "Reminder. In about 5 steps, bear right."
        else:
            return "Reminder. In about 5 steps, continue straight."
    else:  # Standard turn
        return f"Reminder. In about 5 steps, turn {direction}."

def build_post_turn_guidance(current_step, next_step):
    """Generate post-turn guidance that announces the turn made and the next segment.
    Fires immediately after a turn is detected."""
    if not current_step or not next_step:
        return None
    
    curr_maneuver = current_step.get("maneuver", {})
    curr_type = curr_maneuver.get("type", "")
    curr_modifier = curr_maneuver.get("modifier", "")
    
    next_maneuver = next_step.get("maneuver", {})
    next_type = next_maneuver.get("type", "")
    next_modifier = next_maneuver.get("modifier", "")
    next_distance = next_step.get("distance", 0)
    next_st = steps_text(next_distance)
    next_mt = metres_text(next_distance)
    next_name = next_step.get("name", "")
    
    # Describe current action
    if curr_type == "arrive":
        return "You have arrived at your destination."
    elif curr_type in ("turn", "end of road"):
        if "sharp" in curr_modifier and "left" in curr_modifier:
            action = "You turned sharply left."
        elif "sharp" in curr_modifier and "right" in curr_modifier:
            action = "You turned sharply right."
        elif "slight" in curr_modifier and "left" in curr_modifier:
            action = "You turned slightly left."
        elif "slight" in curr_modifier and "right" in curr_modifier:
            action = "You turned slightly right."
        elif "left" in curr_modifier:
            action = "You turned left."
        elif "right" in curr_modifier:
            action = "You turned right."
        elif "uturn" in curr_modifier:
            action = "You made a U-turn."
        else:
            action = "You continued straight."
    elif curr_type == "fork":
        if "left" in curr_modifier:
            action = "You kept left at the fork."
        elif "right" in curr_modifier:
            action = "You kept right at the fork."
        else:
            action = "You continued at the fork."
    else:
        action = None
    
    if not action:
        return None
    
    # Describe next segment and upcoming turn
    if next_type == "arrive":
        return f"{action} Walk {next_st} ({next_mt}) to arrive at your destination."
    else:
        next_direction = maneuver_to_blind_friendly(next_type, next_modifier, 0)
        road_info = f" onto {next_name}" if next_name else ""
        return f"{action} Walk {next_st} ({next_mt}){road_info} to the next turn {next_direction}."

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points on Earth (in meters)."""
    R = 6371000
    la1, lo1, la2, lo2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = la2 - la1, lo2 - lo1
    a = sin(dlat/2)**2 + cos(la1)*cos(la2)*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

# ── ROUTING FUNCTIONS ──────────────────────────────────────────────

def get_route_osrm(slat, slng):
    """Fetch route from OSRM."""
    url = f"{OSRM_BASE}/route/v1/foot/{slng},{slat};{PAINAVU_LNG},{PAINAVU_LAT}"
    
    log.info(f"Trying OSRM: {url}")
    
    try:
        r = requests.get(url, params={"steps": "true"}, headers=HEADERS, timeout=TIMEOUT)
        
        if r.status_code != 200:
            log.error(f"OSRM HTTP {r.status_code}: {r.text}")
            return None
        
        data = r.json()
        
        if data.get("code") != "Ok" or not data.get("routes"):
            msg = data.get("message", "No route")
            log.error(f"OSRM error: {msg}")
            return None
        
        log.info("✅ OSRM route found")
        return data["routes"][0]
        
    except Exception as e:
        log.error(f"OSRM failed: {e}")
        return None

def get_route_ors(slat, slng):
    """Fetch route from OpenRouteService."""
    url = f"{ORS_BASE}/directions/foot-walking"
    
    log.info(f"Trying ORS: {url}")
    
    try:
        body = {
            "coordinates": [[slng, slat], [PAINAVU_LNG, PAINAVU_LAT]],
            "elevation": False,
            "instructions": True,
            "geometry": True
        }
        
        headers = dict(HEADERS)
        headers["Authorization"] = ORS_API_KEY
        
        r = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
        
        if r.status_code != 200:
            log.error(f"ORS HTTP {r.status_code}: {r.text}")
            return None
        
        data = r.json()
        
        if not data.get("routes"):
            log.error("ORS returned no routes")
            return None
        
        log.info("✅ ORS route found")
        return data["routes"][0]
        
    except Exception as e:
        log.error(f"ORS failed: {e}")
        return None

def route_with_fallback(slat, slng):
    """Try ORS first, fall back to OSRM."""
    # Try OpenRouteService first (more reliable)
    route = get_route_ors(slat, slng)
    if route:
        return route, "ORS"
    
    # Fall back to OSRM
    route = get_route_osrm(slat, slng)
    if route:
        return route, "OSRM"
    
    return None, None

def build_instruction(s):
    m       = s.get("maneuver", {})
    mtype   = m.get("type", "")
    mod     = m.get("modifier", "")
    bearing = m.get("bearing_after", 0)
    dist    = s.get("distance", 0)
    road    = s.get("name", "")
    st      = steps_text(dist)
    mt      = metres_text(dist)

    if mtype == "depart":
        # Use blind-friendly "forward" instead of compass direction
        action = "Start walking forward"
    elif mtype == "arrive":
        if   "left"  in mod: return "You have arrived at Painavu. The destination is on your left."
        elif "right" in mod: return "You have arrived at Painavu. The destination is on your right."
        else:                return "You have arrived at Painavu."
    elif mtype in ("turn", "end of road"):
        if   "sharp"  in mod and "left"  in mod: action = "Turn sharply left"
        elif "sharp"  in mod and "right" in mod: action = "Turn sharply right"
        elif "slight" in mod and "left"  in mod: action = "Turn slightly left"
        elif "slight" in mod and "right" in mod: action = "Turn slightly right"
        elif "left"  in mod: action = "Turn left"
        elif "right" in mod: action = "Turn right"
        elif "uturn" in mod: action = "Make a U-turn"
        else: action = "Continue straight"
    elif mtype in ("new name", "continue"):
        if   "left"  in mod: action = "Bear left"
        elif "right" in mod: action = "Bear right"
        else: action = "Continue straight"
    elif mtype == "fork":
        if   "left"  in mod: action = "Keep left at the fork"
        elif "right" in mod: action = "Keep right at the fork"
        else: action = "Continue at the fork"
    elif mtype in ("roundabout", "rotary"):
        ex = m.get("exit", "")
        action = f"Enter the roundabout and take exit {ex}" if ex else "Go through the roundabout"
    elif mtype == "notification":
        return ""
    else:
        action = f"Go {mod}" if mod else "Continue walking"

    road_part = f" onto {road}" if road else ""
    return f"{action}, then walk {st} ({mt}){road_part}."

# ── API ROUTES ────────────────────────────────────────────────────────

@app.route("/")
def index():
    log.info("Serving main page")
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


@app.route("/api/ping", methods=["GET"])
def ping():
    """Simple connectivity test endpoint."""
    return jsonify({"status": "ok", "message": "BlindNav server is running", "timestamp": __import__('time').time()})


@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests to prevent 404 errors."""
    return send_from_directory("static", "manifest.json", mimetype='image/vnd.microsoft.icon')


@app.route("/api/health", methods=["GET"])
def health():
    """Quick check that the server is running and can reach external APIs."""
    errors = []
    # Test Nominatim
    try:
        r = requests.get(f"{NOMINATIM}/status", headers=HEADERS, timeout=10)
        log.info(f"Nominatim status: {r.status_code}")
        if r.status_code != 200:
            errors.append(f"Nominatim returned {r.status_code}")
    except Exception as e:
        errors.append(f"Nominatim unreachable: {e}")

    # Test OSRM
    try:
        r = requests.get(f"{OSRM_BASE}/nearest/v1/foot/76.97,9.84",
                         headers=HEADERS, timeout=10)
        log.info(f"OSRM status: {r.status_code}")
        if r.status_code != 200:
            errors.append(f"OSRM returned {r.status_code}")
    except Exception as e:
        errors.append(f"OSRM unreachable: {e}")

    if errors:
        return jsonify(ok=False, errors=errors), 503
    return jsonify(ok=True, message="All services reachable")


@app.route("/api/locate", methods=["POST"])
def locate():
    d = request.json
    lat, lng = d.get("lat"), d.get("lng")
    if lat is None or lng is None:
        return jsonify(success=False, error="No GPS coordinates provided")

    log.info(f"Reverse geocoding: {lat}, {lng}")
    try:
        r = requests.get(
            f"{NOMINATIM}/reverse",
            params={"lat": lat, "lon": lng, "format": "json",
                    "addressdetails": 1, "zoom": 18},
            headers=HEADERS, timeout=TIMEOUT
        )
        log.info(f"Nominatim response: {r.status_code}")

        if r.status_code != 200:
            return jsonify(success=False,
                           error=f"Geocoding service returned status {r.status_code}")

        data = r.json()
        a = data.get("address", {})
        parts = []
        for k in ("house_number", "road", "suburb", "village",
                  "town", "city", "county", "state"):
            v = a.get(k)
            if v:
                parts.append(v)

        spoken = ", ".join(parts) or data.get("display_name", "Unknown location")
        dist = haversine_distance(lat, lng, PAINAVU_LAT, PAINAVU_LNG)

        return jsonify(success=True, spoken=spoken,
                       full=data.get("display_name", ""),
                       dist_to_painavu=round(dist),
                       lat=lat, lng=lng)

    except requests.exceptions.Timeout:
        log.error("Nominatim timeout")
        return jsonify(success=False, error="Geocoding service timed out. Try again.")
    except requests.exceptions.ConnectionError as e:
        log.error(f"Nominatim connection error: {e}")
        return jsonify(success=False, error="Cannot connect to geocoding service. Check server internet.")
    except Exception as e:
        log.error(f"Locate error: {traceback.format_exc()}")
        return jsonify(success=False, error=f"Server error: {str(e)}")


@app.route("/api/navigate", methods=["POST"])
def navigate():
    d = request.json
    slat, slng = d.get("lat"), d.get("lng")
    if slat is None or slng is None:
        return jsonify(success=False, error="No GPS coordinates provided")

    log.info(f"Route request: ({slat},{slng}) -> Painavu ({PAINAVU_LAT},{PAINAVU_LNG})")

    try:
        # Try ORS first, fall back to OSRM
        route, provider = route_with_fallback(slat, slng)
        
        if not route:
            log.error("Both ORS and OSRM failed to find route")
            return jsonify(success=False, error="No walking route found to Painavu. Check your location and destination.")
        
        log.info(f"✅ Route from {provider}: {route.get('distance'):.0f}m")
        
        # Parse route data (format depends on provider)
        if provider == "ORS":
            total_m = route.get("distance", 0)
            total_s = route.get("duration", 0)
            # ORS returns instructions array directly
            steps_data = route.get("steps", [])
            geometry = route.get("geometry")
        else:  # OSRM
            total_m = route.get("distance", 0)
            total_s = route.get("duration", 0)
            # OSRM returns legs with steps
            steps_data = []
            if "legs" in route:
                for leg in route["legs"]:
                    steps_data.extend(leg.get("steps", []))
            geometry = route.get("geometry")
        
        total_st = steps(total_m)
        mins = max(1, round(total_s / 60))
        hours = mins // 60
        rmins = mins % 60
        
        if hours > 0:
            time_str = f"{hours} hour{'s' if hours>1 else ''} and {rmins} minute{'s' if rmins!=1 else ''}"
        else:
            time_str = f"{mins} minute{'s' if mins!=1 else ''}"
        
        # Build navigation steps
        nav = []
        n = 0
        
        for idx, s in enumerate(steps_data):
            instr = build_instruction(s)
            if not instr:
                continue
            if s.get("distance", 0) < 2 and s.get("maneuver", {}).get("type") not in ("depart", "arrive"):
                continue
            n += 1
            
            # Get maneuver info
            maneuver = s.get("maneuver", {})
            location = maneuver.get("location", [None, None])
            
            nav.append({
                "n":           n,
                "action":      instr,
                "distance":    s.get("distance", 0),
                "step_count":  steps(s.get("distance", 0)),
                "type":        maneuver.get("type", ""),
                "lat":         location[1] if len(location) >= 2 else None,
                "lng":         location[0] if len(location) >= 2 else None
            })
        
        summary = (f"Route to Painavu found via {provider}. "
                   f"Total distance: {metres_text(total_m)}, "
                   f"roughly {total_st} steps, "
                   f"estimated walking time: {time_str}. "
                   f"{len(nav)} direction steps.")
        
        log.info(f"✅ Route: {total_m:.0f}m, {len(nav)} steps via {provider}")
        
        return jsonify(success=True, summary=summary,
                       total_distance=round(total_m, 1),
                       total_duration=round(total_s),
                       total_steps=total_st,
                       nav_steps=nav,
                       geometry=geometry,
                       provider=provider)

    except requests.exceptions.Timeout:
        log.error("Routing timeout")
        return jsonify(success=False, error="Routing service timed out. Try again.")
    except requests.exceptions.ConnectionError as e:
        log.error(f"Routing connection error: {e}")
        return jsonify(success=False,
                       error="Cannot connect to routing service. Check your internet connection.")
    except Exception as e:
        log.error(f"Navigate error: {traceback.format_exc()}")
        return jsonify(success=False, error=f"Server error: {str(e)}")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
