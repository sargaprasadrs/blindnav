"""
BlindNav - Walking navigation assistant for blind users.
Fixed destination: Painavu, Idukki District, Kerala
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import traceback
import logging
from math import radians, sin, cos, atan2, sqrt

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.DEBUG)
log = app.logger


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
PAINAVU_LAT = 9.8465
PAINAVU_LNG = 76.9469
PAINAVU_NAME = "Painavu, Idukki District, Kerala"

# ── CONFIG ────────────────────────────────────────────────────────────
STEP_LENGTH = 0.65
OSRM_BASE = "https://router.project-osrm.org"
NOMINATIM = "https://nominatim.openstreetmap.org"
ORS_BASE = "https://api.openrouteservice.org/v2"
ORS_API_KEY = "5b3ce3597851110001cf6248"
HEADERS = {
    "User-Agent": "BlindNav/1.0 (accessibility-project; contact@blindnav.org)",
    "Accept": "application/json"
}
TIMEOUT = 20


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


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    la1, lo1, la2, lo2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = la2 - la1, lo2 - lo1
    a = sin(dlat / 2) ** 2 + cos(la1) * cos(la2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def direction_word(modifier):
    """Convert OSRM modifier to simple blind-friendly word."""
    if not modifier:
        return "forward"
    mod = modifier.lower().replace(" ", "")
    if mod == "straightahead":
        return "forward"
    elif "sharpleft" in mod or ("sharp" in mod and "left" in mod):
        return "sharply left"
    elif "sharpright" in mod or ("sharp" in mod and "right" in mod):
        return "sharply right"
    elif "slightleft" in mod or ("slight" in mod and "left" in mod):
        return "slightly left"
    elif "slightright" in mod or ("slight" in mod and "right" in mod):
        return "slightly right"
    elif "left" in mod:
        return "left"
    elif "right" in mod:
        return "right"
    elif "uturn" in mod:
        return "back around"
    else:
        return "forward"


def build_instruction(s):
    m = s.get("maneuver", {})
    mtype = m.get("type", "")
    mod = m.get("modifier", "")
    dist = s.get("distance", 0)
    road = s.get("name", "")
    st = steps_text(dist)
    mt = metres_text(dist)
    dw = direction_word(mod)

    if mtype == "depart":
        action = "Start walking forward"
    elif mtype == "arrive":
        if "left" in mod:
            return "You have arrived at Painavu, and the destination is on your left."
        elif "right" in mod:
            return "You have arrived at Painavu, and the destination is on your right."
        else:
            return "You have arrived at Painavu."
    elif mtype in ("turn", "end of road"):
        action = f"Turn {dw}"
    elif mtype in ("new name", "continue"):
        if "left" in mod:
            action = "Bear left"
        elif "right" in mod:
            action = "Bear right"
        else:
            action = "Continue straight"
    elif mtype == "fork":
        if "left" in mod:
            action = "Keep left at the fork"
        elif "right" in mod:
            action = "Keep right at the fork"
        else:
            action = "Continue at the fork"
    elif mtype in ("roundabout", "rotary"):
        ex = m.get("exit", "")
        action = f"Enter the roundabout and take exit {ex}" if ex else "Go through the roundabout"
    elif mtype == "notification":
        return ""
    else:
        action = f"Go {mod}" if mod else "Continue walking"

    road_part = f" onto {road}" if road else ""
    return f"{action}, and then walk {st} ({mt}){road_part}."


# ── ROUTING FUNCTIONS ──────────────────────────────────────────────

def get_route_osrm(slat, slng):
    url = f"{OSRM_BASE}/route/v1/foot/{slng},{slat};{PAINAVU_LNG},{PAINAVU_LAT}"
    log.info(f"Trying OSRM: {url}")
    try:
        r = requests.get(url, params={"steps": "true", "geometries": "geojson", "overview": "full"},
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            log.error(f"OSRM HTTP {r.status_code}: {r.text}")
            return None
        data = r.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            log.error(f"OSRM error: {data.get('message', 'No route')}")
            return None
        log.info("✅ OSRM route found")
        return data["routes"][0]
    except Exception as e:
        log.error(f"OSRM failed: {e}")
        return None


def get_route_ors(slat, slng):
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
    route = get_route_ors(slat, slng)
    if route:
        return route, "ORS"
    route = get_route_osrm(slat, slng)
    if route:
        return route, "OSRM"
    return None, None


# ── API ROUTES ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "message": "BlindNav server is running",
                    "timestamp": __import__('time').time()})


@app.route('/favicon.ico')
def favicon():
    return send_from_directory("static", "manifest.json", mimetype='image/vnd.microsoft.icon')


@app.route("/api/health", methods=["GET"])
def health():
    errors = []
    try:
        r = requests.get(f"{NOMINATIM}/status", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            errors.append(f"Nominatim returned {r.status_code}")
    except Exception as e:
        errors.append(f"Nominatim unreachable: {e}")
    try:
        r = requests.get(f"{OSRM_BASE}/nearest/v1/foot/76.97,9.84", headers=HEADERS, timeout=10)
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
            params={"lat": lat, "lon": lng, "format": "json", "addressdetails": 1, "zoom": 18},
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code != 200:
            return jsonify(success=False, error=f"Geocoding service returned status {r.status_code}")
        data = r.json()
        a = data.get("address", {})
        parts = []
        for k in ("house_number", "road", "suburb", "village", "town", "city", "county", "state"):
            v = a.get(k)
            if v:
                parts.append(v)
        spoken = ", ".join(parts) or data.get("display_name", "Unknown location")
        dist = haversine_distance(lat, lng, PAINAVU_LAT, PAINAVU_LNG)
        return jsonify(success=True, spoken=spoken, full=data.get("display_name", ""),
                       dist_to_painavu=round(dist), lat=lat, lng=lng)
    except requests.exceptions.Timeout:
        return jsonify(success=False, error="Geocoding service timed out. Try again.")
    except requests.exceptions.ConnectionError as e:
        return jsonify(success=False, error="Cannot connect to geocoding service.")
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
        route, provider = route_with_fallback(slat, slng)

        if not route:
            return jsonify(success=False,
                           error="No walking route found to Painavu. Check your location and destination.")

        if provider == "ORS":
            total_m = route.get("distance", 0)
            total_s = route.get("duration", 0)
            steps_data = route.get("steps", [])
            geometry = route.get("geometry")
        else:
            total_m = route.get("distance", 0)
            total_s = route.get("duration", 0)
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
            time_str = f"{hours} hour{'s' if hours > 1 else ''} and {rmins} minute{'s' if rmins != 1 else ''}"
        else:
            time_str = f"{mins} minute{'s' if mins != 1 else ''}"

        nav = []
        n = 0

        for idx, s in enumerate(steps_data):
            instr = build_instruction(s)
            if not instr:
                continue
            if s.get("distance", 0) < 2 and s.get("maneuver", {}).get("type") not in ("depart", "arrive"):
                continue
            n += 1

            maneuver = s.get("maneuver", {})
            location = maneuver.get("location", [None, None])
            mod = maneuver.get("modifier", "")

            # Pre-compute the turn direction for this step (what turn happens AT this point)
            turn_direction = direction_word(mod)
            mtype = maneuver.get("type", "")

            # Look ahead: after completing this step's walk, what's the next turn?
            next_turn_dir = None
            next_turn_type = None
            if idx + 1 < len(steps_data):
                next_m = steps_data[idx + 1].get("maneuver", {})
                next_turn_dir = direction_word(next_m.get("modifier", ""))
                next_turn_type = next_m.get("type", "")

            nav.append({
                "n": n,
                "action": instr,
                "distance": s.get("distance", 0),
                "step_count": steps(s.get("distance", 0)),
                "type": mtype,
                "modifier": mod,
                "turn_direction": turn_direction,
                "next_turn_direction": next_turn_dir,
                "next_turn_type": next_turn_type,
                "road": s.get("name", ""),
                "lat": location[1] if len(location) >= 2 else None,
                "lng": location[0] if len(location) >= 2 else None
            })

        summary = (f"Route to Painavu found. "
                   f"Total distance is {metres_text(total_m)}, "
                   f"and that is roughly {total_st} steps, "
                   f"and estimated walking time is {time_str}. "
                   f"There are {len(nav)} direction steps.")

        log.info(f"✅ Route: {total_m:.0f}m, {len(nav)} steps via {provider}")

        return jsonify(success=True, summary=summary,
                       total_distance=round(total_m, 1),
                       total_duration=round(total_s),
                       total_steps=total_st,
                       nav_steps=nav,
                       geometry=geometry,
                       provider=provider)

    except requests.exceptions.Timeout:
        return jsonify(success=False, error="Routing service timed out. Try again.")
    except requests.exceptions.ConnectionError:
        return jsonify(success=False, error="Cannot connect to routing service.")
    except Exception as e:
        log.error(f"Navigate error: {traceback.format_exc()}")
        return jsonify(success=False, error=f"Server error: {str(e)}")


@app.route("/api/reroute", methods=["POST"])
def reroute():
    """Re-calculate route from current position when user goes off-track."""
    d = request.json
    slat, slng = d.get("lat"), d.get("lng")
    if slat is None or slng is None:
        return jsonify(success=False, error="No GPS coordinates provided")

    log.info(f"REROUTE request from ({slat},{slng})")

    try:
        route, provider = route_with_fallback(slat, slng)
        if not route:
            return jsonify(success=False, error="Cannot find a new route from your position.")

        if provider == "ORS":
            total_m = route.get("distance", 0)
            total_s = route.get("duration", 0)
            steps_data = route.get("steps", [])
            geometry = route.get("geometry")
        else:
            total_m = route.get("distance", 0)
            total_s = route.get("duration", 0)
            steps_data = []
            if "legs" in route:
                for leg in route["legs"]:
                    steps_data.extend(leg.get("steps", []))
            geometry = route.get("geometry")

        total_st = steps(total_m)

        nav = []
        n = 0
        for idx, s in enumerate(steps_data):
            instr = build_instruction(s)
            if not instr:
                continue
            if s.get("distance", 0) < 2 and s.get("maneuver", {}).get("type") not in ("depart", "arrive"):
                continue
            n += 1
            maneuver = s.get("maneuver", {})
            location = maneuver.get("location", [None, None])
            mod = maneuver.get("modifier", "")
            mtype = maneuver.get("type", "")
            turn_direction = direction_word(mod)

            next_turn_dir = None
            next_turn_type = None
            if idx + 1 < len(steps_data):
                next_m = steps_data[idx + 1].get("maneuver", {})
                next_turn_dir = direction_word(next_m.get("modifier", ""))
                next_turn_type = next_m.get("type", "")

            nav.append({
                "n": n,
                "action": instr,
                "distance": s.get("distance", 0),
                "step_count": steps(s.get("distance", 0)),
                "type": mtype,
                "modifier": mod,
                "turn_direction": turn_direction,
                "next_turn_direction": next_turn_dir,
                "next_turn_type": next_turn_type,
                "road": s.get("name", ""),
                "lat": location[1] if len(location) >= 2 else None,
                "lng": location[0] if len(location) >= 2 else None
            })

        return jsonify(success=True,
                       total_distance=round(total_m, 1),
                       total_duration=round(total_s),
                       total_steps=total_st,
                       nav_steps=nav,
                       geometry=geometry,
                       provider=provider,
                       rerouted=True)

    except Exception as e:
        log.error(f"Reroute error: {traceback.format_exc()}")
        return jsonify(success=False, error=f"Reroute failed: {str(e)}")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)