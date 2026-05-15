# Slopsmith Tuner Plugin

A real-time guitar and bass tuner plugin for [Slopsmith](https://github.com/byrongamatos/slopsmith).

<img width="315" height="444" alt="grafik" src="https://github.com/user-attachments/assets/1cde859e-d978-416a-b68b-5f4fda218309" />


This plugin adds a floating "Tuner" button to the Slopsmith interface, providing a high-accuracy chromatic tuner with support for multiple presets, custom tunings, and automatic song tuning detection.

## Features

- **Real-time Pitch Detection**: Uses the YIN algorithm for robust and accurate frequency tracking.
- **Multiple Presets**: Includes common guitar and bass tunings (Standard, Drop D, DADGAD, Open G, etc.).
- **Automatic Song Tuning**: Detects and selects the correct tuning for the currently playing song in the Slopsmith player.
- **Manual & Auto Tracking**: Automatically estimates the closest string or allows manual selection for focused tuning.
- **Visual Feedback**: Large cents-deviation gauge, frequency display, and color-coded indicators.
- **Custom Tunings**: Add your own tunings via note names (e.g., E2, A2) or Hz frequencies in the settings.
- **Audio Device Selection**: Choose specific input devices and channels (Mono, Left, Right) for professional interfaces.
- **Themable UI**: Styled with Tailwind CSS to match your Slopsmith theme.

## Installation

```bash
cd /path/to/slopsmith/plugins
git clone https://github.com/OmikronApex/slopsmith-plugin-tuner.git tuner
# Restart Slopsmith (or restart your docker container)
docker compose restart
```

## How to Use

1. Click the **Tuner** button at the bottom-right of the screen (or the "Tuner" button in the player controls).
2. The tuner will automatically default to the **Current Song** tuning if you are in the player.
3. Select other presets or custom tunings from the dropdown menu if needed.
4. Pluck a string. The tuner will automatically detect the closest string in the selected tuning.
5. (Optional) Click a specific note button in the tuner window to lock onto that string (useful for very out-of-tune strings).
6. Adjust your tuning until the needle is centered and the indicator turns green.

## Configuration

### In-App Settings
Click the ⚙️ icon in the tuner window to access:
- **Audio Input**: Select your preferred microphone or audio interface.
- **Channel Selection**: Choose between Mono (mixed), Left, or Right channels (ideal for multi-channel audio interfaces).

<img width="306" height="242" alt="grafik" src="https://github.com/user-attachments/assets/41746a5b-bee9-4358-a10a-0eee8d5651b5" />


### Plugin Manager
Access advanced settings via the Slopsmith Plugin Manager (Settings -> Plugins -> Tuner):
- **Floating Button**: Toggle the visibility of the tuner button on the main interface.
- **Tuning Visibility**: Toggle which built-in tunings appear in your menu.
- **Custom Tunings**: Define your own tuning presets by entering a name and a list of notes/frequencies.

<img width="640" height="1025" alt="grafik" src="https://github.com/user-attachments/assets/d67585a2-f376-44bb-8c9b-64a0de732dbd" />


## License

MIT
