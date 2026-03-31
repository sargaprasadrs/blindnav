## Raspberry Pi Notes

Yes, the backend in this repo should run on a Raspberry Pi.

Why it should work:
- The Python server uses only `Flask`, `Flask-Cors`, and `requests`.
- There are no Windows-only Python modules in `app.py`.
- The `ngrok.exe` file is Windows-specific, but it is optional and not needed on the Pi.

Important caveats:
- The frontend depends on browser geolocation (`navigator.geolocation`).
- It also uses browser speech synthesis and optional motion sensors.
- The app calls external services, so the Pi needs internet access.
- The map UI loads Leaflet from a CDN, so that also needs internet access.

Best way to use it on a Pi:
- Run the Flask server on the Raspberry Pi.
- Open the app from a phone, not the Pi desktop, so the phone provides GPS.
- Serve it over HTTPS if you want browser geolocation to work reliably off-device.

If you open it directly in a Pi desktop browser:
- The server should start.
- The full navigation experience may not work unless that Pi/browser setup exposes location data.

## Setup

Clone the repo on the Pi, then run:

```bash
chmod +x setup_rpi.sh
./setup_rpi.sh
```

That script will:
- create `.venv`
- upgrade `pip`
- install everything from `requirements.txt`

## Manual setup

If you prefer the commands directly:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Then access:

```text
http://localhost:5000
```

From another device on the same network, use:

```text
http://<pi-ip>:5000
```

If geolocation does not work from another device, the usual fix is to put the app behind HTTPS.
