# HandTracker HUD

A computer vision-powered hand tracking application that creates an interactive heads-up display (HUD) for controlling Spotify and other applications using hand gestures and voice commands.

## Features

- **Hand Gesture Control**: Use hand gestures to control Spotify playback (play/pause, next/previous track)
- **Volume Control**: Adjust volume using pinch gestures
- **Voice Commands**: Control apps using voice recognition with Google Speech API
- **Interactive Quad Window**: Create resizable, draggable virtual windows using hand gestures
- **Spotify Integration**: Real-time display of currently playing track with album artwork
- **Multi-App Support**: Framework for spawning different app interfaces (Spotify, YouTube, etc.)
- **Real-time HUD**: Overlay interface that responds to hand tracking in real-time

## Technologies Used

- **Computer Vision**: MediaPipe for hand landmark detection
- **Audio Control**: Spotify Web API integration
- **Voice Recognition**: Google Speech Recognition API
- **GUI**: OpenCV for real-time video processing and UI rendering
- **macOS Integration**: PyObjC for system-level controls

## Requirements

- Python 3.11+
- Webcam
- Spotify Premium account
- macOS (for system integration features)
- Microphone (for voice commands)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/lawrenceDegoma/HandTrackerHUD.git
cd HandTrackerHUD
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Spotify API credentials:
   - Create a Spotify app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a `.env` file with your credentials:
```env
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8080/callback
```

## Usage

Run the application:
```bash
python src/main.py
```

### Controls

- **ESC**: Exit application
- **C**: Clear tracking points
- **V**: Toggle volume gesture mode
- **M**: Toggle voice control

### Hand Gestures

- **Pinch**: Interact with UI elements, drag windows, control volume
- **Open Palm**: Navigate and select interface elements
- **Quadrilateral Formation**: Create resizable app windows

### Voice Commands

- "Open Spotify" - Launch Spotify mini-player
- "Play/Pause" - Control playback
- "Next/Previous" - Skip tracks

## 🎯 Future Enhancements

- Support for additional streaming services
- Gesture customization
- Multi-hand tracking
- Enhanced voice command vocabulary
- Cross-platform compatibility

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source. Please check the license file for details.

---
