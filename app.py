"""
BlindNav - Walking navigation assistant for blind users.
Fixed destination: Painavu, Idukki District, Kerala (9.8453, 76.9730)
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
import traceback
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
log = app.logger

# ── FIXED DESTINATION ─────────────────────────────────────────────────
PAINAVU_LAT  = 9.8453
PAINAVU_LNG  = 76.9730
PAINAVU_NAME = "Painavu, Idukki District, Kerala"

# ── CONFIG ────────────────────────────────────────────────────────────
STEP_LENGTH  = 0.65
OSRM_BASE    = "https://router.project-osrm.org"
NOMINATIM    = "https://nominatim.openstreetmap.org"
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

def haversine_distance(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371000
    la1, lo1, la2, lo2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = la2 - la1, lo2 - lo1
    a = sin(dlat/2)**2 + cos(la1)*cos(la2)*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

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
        action = f"Start walking {cardinal(bearing)}"
    elif mtype == "arrive":
        if   "left"  in mod: return "You have arrived at Painavu. The destination is on your left."
        elif "right" in mod: return "You have arrived at Painavu. The destination is on your right."
        else:                return "You have arrived at Painavu."
    elif mtype in ("turn", "end of road"):
        if   "sharp"  in mod and "left"  in mod: action = "Take a sharp left turn"
        elif "sharp"  in mod and "right" in mod: action = "Take a sharp right turn"
        elif "slight" in mod and "left"  in mod: action = "Turn slightly to the left"
        elif "slight" in mod and "right" in mod: action = "Turn slightly to the right"
        elif "left"  in mod: action = "Turn left"
        elif "right" in mod: action = "Turn right"
        elif "uturn" in mod: action = "Make a U-turn"
        else: action = "Continue straight ahead"
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

    road_part = f" along {road}" if road else ""
    return f"{action}, then walk {st} ({mt}){road_part}."

# ── API ROUTES ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


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
        url = (f"{OSRM_BASE}/route/v1/foot/"
               f"{slng},{slat};{PAINAVU_LNG},{PAINAVU_LAT}")

        log.info(f"OSRM URL: {url}")

        r = requests.get(
            url,
            params={"overview": "full", "steps": "true", "geometries": "geojson"},
            headers=HEADERS, timeout=TIMEOUT
        )

        log.info(f"OSRM response: {r.status_code}")

        if r.status_code != 200:
            return jsonify(success=False,
                           error=f"Routing service returned status {r.status_code}")

        data = r.json()
        log.info(f"OSRM code: {data.get('code')}")

        if data.get("code") != "Ok" or not data.get("routes"):
            msg = data.get("message", "No walking route found to Painavu")
            return jsonify(success=False, error=msg)

        route    = data["routes"][0]
        total_m  = route["distance"]
        total_s  = route["duration"]
        total_st = steps(total_m)
        mins     = max(1, round(total_s / 60))
        hours    = mins // 60
        rmins    = mins % 60

        if hours > 0:
            time_str = f"{hours} hour{'s' if hours>1 else ''} and {rmins} minute{'s' if rmins!=1 else ''}"
        else:
            time_str = f"{mins} minute{'s' if mins!=1 else ''}"

        nav = []
        n = 0
        for leg in route["legs"]:
            for s in leg["steps"]:
                instr = build_instruction(s)
                if not instr:
                    continue
                if s["distance"] < 2 and s["maneuver"]["type"] not in ("depart", "arrive"):
                    continue
                n += 1
                nav.append({
                    "n":           n,
                    "action":      instr,  # Changed from instruction to action
                    "distance":    round(s["distance"], 1),  # Changed from meters to distance  
                    "step_count":  steps(s["distance"]),  # Changed from steps to step_count
                    "type":        s["maneuver"].get("type", ""),
                    "lat":         s["maneuver"]["location"][1] if len(s["maneuver"].get("location", [])) >= 2 else None,
                    "lng":         s["maneuver"]["location"][0] if len(s["maneuver"].get("location", [])) >= 2 else None
                })

        summary = (f"Route to Painavu found. "
                   f"Total distance: {metres_text(total_m)}, "
                   f"roughly {total_st} steps, "
                   f"estimated walking time: {time_str}. "
                   f"{len(nav)} direction steps.")

        log.info(f"Route: {total_m:.0f}m, {len(nav)} steps")

        return jsonify(success=True, summary=summary,
                       total_m=round(total_m, 1),
                       total_s=round(total_s),
                       total_steps=total_st,
                       nav_steps=nav,
                       geometry=route["geometry"])

    except requests.exceptions.Timeout:
        log.error("OSRM timeout")
        return jsonify(success=False, error="Routing service timed out. Try again.")
    except requests.exceptions.ConnectionError as e:
        log.error(f"OSRM connection error: {e}")
        return jsonify(success=False,
                       error="Cannot connect to routing service. Check server internet connection.")
    except Exception as e:
        log.error(f"Navigate error: {traceback.format_exc()}")
        return jsonify(success=False, error=f"Server error: {str(e)}")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)