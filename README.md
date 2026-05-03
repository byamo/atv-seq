# atv-seq

**Skip those endless credits and get to the next episode instantly!**

`atv-seq` is a command-line tool that executes pre-defined command sequences on your Apple TV using the [pyatv](https://pyatv.dev) library. Perfect for skipping long end credits or automating any repetitive remote control actions.

## Features

- **Custom sequences**: Define any sequence of remote control actions in JSON
- **Modular**: Use different sequence files for different scenarios
- **Pairing support**: Securely pair with your Apple TV and save credentials
- **IP from credentials**: Automatically uses the IP address from stored pairing credentials
- **Simple CLI**: Easy to use command-line interface

## Installation

### From GitHub (recommended)

```bash
pipx install git+https://github.com/byamo/atv-seq.git
```

### From local source

```bash
cd atv-seq
pipx install -e .
```

## Requirements

- Python 3.10+
- An Apple TV on the same network
- pyatv library (installed automatically)

## Usage

### First time: Pair your Apple TV

Before you can control your Apple TV, you need to pair with it. The IP address will be automatically saved for future use:

```bash
atv-seq --pair
```

Follow the on-screen instructions. You'll need to enter a PIN that appears on your Apple TV or enter the displayed PIN on your device.

Credentials (including IP address) are saved automatically in `credentials.json` and reused for future connections.

### Run a sequence

Execute the default sequence (skip to next episode). The script automatically uses the IP from stored credentials:

```bash
atv-seq
```

### Use a custom sequence

```bash
atv-seq -s /path/to/your_sequence.json
```

### Specify Apple TV IP explicitly

If you have multiple Apple TVs or need to override the stored IP:

```bash
atv-seq --ip 10.0.0.100 -s your_sequence.json
```

This will also update the credentials storage with the new IP address.

## Sequence File Format

Sequences are defined in JSON files with the following structure:

```json
{
  "name": "Skip Intro",
  "description": "Navigates to next episode",
  "steps": [
    {"action": "select", "delay": 0.5},
    {"action": "up", "delay": 0.3},
    {"action": "right", "delay": 0.3},
    {"action": "select", "delay": 0}
  ]
}
```

### Available Actions

All standard Apple TV remote control actions are supported:

- Navigation: `up`, `down`, `left`, `right`, `select`
- Playback: `play`, `pause`, `play_pause`, `stop`, `next`, `previous`
- Volume: `volume_up`, `volume_down`, `mute`
- Menu: `menu`, `home`, `top_menu`
- Power: `wake`, `sleep`

### Delay

The `delay` field (in seconds) controls how long to wait after each action. This is useful for giving the Apple TV time to respond between commands.

## Examples

### Skip streaming intro

```json
{
  "name": "Skip End Credits",
  "steps": [
    {"action": "select", "delay": 0.5},
    {"action": "down", "delay": 0.2},
    {"action": "down", "delay": 0.2},
    {"action": "select", "delay": 0}
  ]
}
```

### Increase volume

```json
{
  "name": "Volume Up x3",
  "steps": [
    {"action": "volume_up", "delay": 0.1},
    {"action": "volume_up", "delay": 0.1},
    {"action": "volume_up", "delay": 0.1}
  ]
}
```

### Go to home and open app

```json
{
  "name": "Home to App",
  "steps": [
    {"action": "home", "delay": 1.0},
    {"action": "right", "delay": 0.5},
    {"action": "right", "delay": 0.5},
    {"action": "select", "delay": 0}
  ]
}
```

## Default Sequence

The default sequence (`default.json`) performs the typical "next episode" navigation:
`select -> up -> right -> select`.

This works for some streaming apps to skip end credits and go to the next episode.

## IP Address Management

The script automatically manages IP addresses:

- **First use**: Run `atv-seq --pair` to discover and pair with your Apple TV. The IP is automatically saved.
- **Subsequent uses**: Simply run `atv-seq` - the script uses the IP from stored credentials.
- **Multiple devices**: Use `--ip` to specify which Apple TV to target. The script will update credentials for that IP.
- **View stored IP**: Check `atv_seq/credentials.json` to see saved configurations.

## Creating Custom Sequences

1. Create a new JSON file with your sequence
2. Test it with: `atv-seq -s your_sequence.json`
3. Adjust delays if commands execute too fast
4. Save it for later use

## Project Structure

```
atv-seq/
├── atv_seq/
│   ├── __init__.py
│   ├── __main__.py          # Main script
│   ├── default.json         # Default skip sequence
│   └── credentials.json     # Pairing credentials (generated, gitignored)
├── .gitignore
├── MANIFEST.in
├── pyproject.toml
└── README.md
```

## Troubleshooting

### Some actions don't work
- Try to increase the `--delay-factor` to slow down actions

### "No IP address specified and no stored credentials found"
- Run `atv-seq --pair` first to pair and save your Apple TV's IP
- Or specify an IP manually with `--ip 10.0.0.100`

### "No device found"
- Verify the Apple TV is on and connected to the same network
- Check the IP address with `cat atv_seq/credentials.json`
- Make sure your computer can ping the Apple TV: `ping <IP>`
- Your Apple TV's IP may have changed - run `--pair` again

### "Pairing required"
- Run `atv-seq --pair` first
- Follow the pairing instructions on screen
- If pairing fails, delete `credentials.json` and try again

### "Action not supported"
- The action may not be available on your Apple TV model
- The script uses Companion protocol for navigation commands
- Check the available actions in the pyatv documentation
- Try using only: `select`, `up`, `down`, `left`, `right`

### Commands not executing
- **Most common cause**: Pairing was not completed successfully
- Verify Companion protocol is available: look for `Companion` in the service list when running the script
- Run `atv-seq --pair` again and ensure you complete the pairing process
- The default sequence requires Companion protocol for navigation commands

### Connection issues
- Restart your Apple TV
- Forget the device: remove `credentials.json` and run `--pair` again
- Check your firewall allows local network connections

## License

MIT License - feel free to use, modify, and distribute.

## Credits

Built with [pyatv](https://github.com/postlund/pyatv) - A Python library for Apple TV and AirPlay devices.
