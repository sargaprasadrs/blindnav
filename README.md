# BlindNav — Walking Navigation Assistant for Blind Users

An accessible walking navigation app designed specifically for blind and visually impaired users. BlindNav provides automatic, real-time voice guidance during walking navigation with a fixed destination to **Painavu, Idukki District, Kerala**.

## 🎯 Features

### Live Navigation
- **Automatic GPS Tracking** - Continuous location monitoring every 2 seconds
- **Proactive Voice Directions** - No button presses needed, directions announced automatically
- **Step-by-Step Guidance** - Turn alerts at multiple distances (100m, 50m, 30m, 20m, 10m, 5m, 3m)
- **Step Counting** - Calculates walking steps based on GPS movement (0.65m per step)
- **Off-Route Detection** - Alerts when deviating more than 50m from planned route
- **Automatic Rerouting** - Recalculates route when user goes off-track

### Accessibility First
- **Voice-First Design** - Works entirely through audio cues
- **Natural Language Instructions** - Clear, simple directions like "Turn left in 10 steps"
- **Gesture Support** - Shake phone to repeat current instruction
- **Keyboard Shortcuts** - Full keyboard navigation support
- **Screen Reader Compatible** - ARIA labels and live regions
- **High Contrast UI** - Dark theme with clear visual indicators

### Smart Guidance
- **Progressive Warnings** - Early alerts (20 steps), medium alerts (10 steps), urgent alerts (3 steps)
- **Context Awareness** - Different instructions for turns, forks, roundabouts, U-turns
- **Road Information** - Includes road names when available
- **Arrival Announcements** - Clear notification when reaching destination

## 📋 Prerequisites

- **Python 3.8+** (for backend)
- **Node.js 16+** (for frontend build, optional)
- **Modern Web Browser** with GPS support (Chrome, Firefox, Safari, Edge)
- **Internet Connection** (for routing and geocoding APIs)

## 🚀 Installation

### Step 1: Clone the Repository

```bash
git clone <your-repository-url>
cd blindnav
```

### Step 2: Set Up Python Backend

#### Create Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install Flask==3.0.0 Flask-Cors==4.0.0 requests==2.31.0
```

### Step 3: Set Up Frontend (Optional)

The frontend is a single HTML file that runs directly in the browser. No build step required. However, if you want to use a development server:

```bash
npm install
npm run dev
```

### Step 4: Create Required Directories

```bash
# Create static folder for manifest and assets
mkdir static
```

Copy the `manifest.json` file to the `static/` folder.

## ▶️ Running the Application

### Start the Backend Server

```bash
# Make sure virtual environment is activated
python app.py
```

The server will start at: **http://localhost:5000**

### Open in Browser

1. Open your web browser
2. Navigate to `http://localhost:5000`
3. **Allow GPS/Location permission** when prompted
4. Wait for GPS signal to acquire
5. Tap **"Enable GPS Location"** button
6. Tap **"Where Am I?"** to test location
7. Toggle **"Navigate to Painavu"** to start live navigation

## 📱 Mobile Usage

For best mobile experience:

1. Access the app on your phone's browser
2. Add to home screen (PWA support)
3. Enable location services
4. Keep screen on during navigation (wake lock enabled)

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `W` | Get current location ("Where Am I?") |
| `R` | Repeat current instruction |
| `Space` | Toggle navigation on/off |
| `Escape` | Stop navigation |

## 🎮 Gestures (Mobile)

| Gesture | Action |
|---------|--------|
| Shake Phone | Repeat current instruction |
| Tap Toggle | Start/Stop navigation |

## 🔧 Configuration

### Fixed Destination

The app is configured with a fixed destination:

```python
PAINAVU_LAT = 9.853500
PAINAVU_LNG = 76.947520
PAINAVU_NAME = "Painavu, Idukki District, Kerala"
```

To change the destination, modify these values in `app.py`.

### Step Length

Default walking step length is 0.65 meters. Adjust in `app.py`:

```python
STEP_LENGTH = 0.65
```

### API Services

The app uses these free services:

| Service | Purpose | URL |
|---------|---------|-----|
| OSRM | Walking routes | `https://router.project-osrm.org` |
| ORS | Alternative routing | `https://api.openrouteservice.org` |
| Nominatim | Reverse geocoding | `https://nominatim.openstreetmap.org` |

## 📁 Project Structure

```
blindnav/
├── app.py                 # Flask backend server
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Main frontend (single-page app)
├── static/
│   └── manifest.json     # PWA manifest
├── README.md             # This file
└── .venv/                # Python virtual environment (gitignored)
```

## 🐛 Troubleshooting

### GPS Not Working

1. Ensure location services are enabled on your device
2. Grant location permission to the browser
3. Try the test map (click "Toggle test map" in debug section)
4. Use HTTPS in production (GPS requires secure context)

### No Route Found

1. Check your internet connection
2. Verify you're not in a remote area without map data
3. Try moving to a different location
4. Check server logs for API errors

### Voice Not Speaking

1. Check browser volume settings
2. Ensure speech synthesis is supported (check browser compatibility)
3. Try a different browser (Chrome has best support)

### Server Won't Start

1. Ensure Python 3.8+ is installed
2. Check if port 5000 is available
3. Verify all dependencies are installed
4. Check for Python path issues

## 🔐 Privacy & Security

- **No Data Storage** - Location data is not stored on the server
- **Client-Side Processing** - Most navigation logic runs in the browser
- **External APIs** - Location data is sent to OSRM/Nominatim for routing
- **HTTPS Required** - Use HTTPS in production for GPS access

## 📄 License

This project is open source. Feel free to modify and distribute.

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- Additional destination support
- Offline map caching
- Multiple language support
- Enhanced accessibility features
- Better battery optimization

## 📞 Support

For issues or questions:

1. Check the troubleshooting section
2. Review server logs for errors
3. Test with the debug map feature
4. Ensure all dependencies are properly installed

## 🙏 Acknowledgments

- **OpenStreetMap** - Map data
- **OSRM** - Routing engine
- **OpenRouteService** - Alternative routing
- **Nominatim** - Geocoding service
- **Leaflet** - Map library

---

**Built with accessibility in mind** ♿ | **Voice-first navigation** 🎤 | **Free and open source** 🆓
