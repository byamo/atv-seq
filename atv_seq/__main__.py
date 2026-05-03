#!/usr/bin/env python3
"""atv-seq: Execute command sequences on Apple TV via pyatv."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyatv import connect, pair, scan
from pyatv.const import PairingRequirement, Protocol

if TYPE_CHECKING:
    from pyatv.conf import AppleTV as AppleTVConfig


CREDENTIALS_FILE: Path = Path(__file__).parent / "credentials.json"
DEFAULT_SEQUENCE_FILE: Path = Path(__file__).parent / "default.json"


def get_version() -> str:
    """Read version from pyproject.toml.

    Returns:
        str: The version string from pyproject.toml.

    """
    pyproject_path: Path = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        import tomllib

        data: dict[str, Any] = tomllib.load(f)
    return data["project"]["version"]


VERSION: str = get_version()


def get_stored_ip() -> str | None:
    """Get IP address from stored credentials.

    Returns:
        str | None: The first stored IP address, or None if no credentials exist.

    """
    if not CREDENTIALS_FILE.exists():
        return None

    with CREDENTIALS_FILE.open("r") as f:
        data: dict[str, Any] = json.load(f)

    # Return the first IP that has credentials
    for ip in data:
        return ip
    return None


def get_stored_ips() -> list[str]:
    """Get all stored IP addresses from credentials.

    Returns:
        list[str]: List of all stored IP addresses.

    """
    if not CREDENTIALS_FILE.exists():
        return []

    with CREDENTIALS_FILE.open("r") as f:
        data: dict[str, Any] = json.load(f)

    return list(data.keys())


async def save_credentials(address: str, protocol: Protocol, credentials: str) -> None:
    """Save credentials to a JSON file.

    Args:
        address: The IP address of the Apple TV.
        protocol: The protocol used (e.g., Protocol.Companion).
        credentials: The credentials string to save.

    """
    exists: bool = await asyncio.to_thread(CREDENTIALS_FILE.exists)
    data: dict[str, Any] = {}
    if exists:
        content: str = await asyncio.to_thread(CREDENTIALS_FILE.read_text)
        data = json.loads(content)

    if address not in data:
        data[address] = {}
    data[address][protocol.name] = credentials

    await asyncio.to_thread(
        CREDENTIALS_FILE.write_text,
        json.dumps(data, indent=2),
    )


async def load_credentials(address: str, protocol: Protocol) -> str | None:
    """Load credentials from JSON file.

    Args:
        address: The IP address of the Apple TV.
        protocol: The protocol used (e.g., Protocol.Companion).

    Returns:
        str | None: The credentials string, or None if not found.

    """
    exists: bool = await asyncio.to_thread(CREDENTIALS_FILE.exists)
    if not exists:
        return None

    content: str = await asyncio.to_thread(CREDENTIALS_FILE.read_text)
    data: dict[str, Any] = json.loads(content)

    return data.get(address, {}).get(protocol.name)


def remove_credentials(address: str | None = None) -> bool:
    """Remove credentials from JSON file.

    Args:
        address: The IP address to remove. If None, removes all credentials.

    Returns:
        bool: True if credentials were removed, False otherwise.

    """
    if not CREDENTIALS_FILE.exists():
        print("No credentials file found.")
        return False

    with CREDENTIALS_FILE.open("r") as f:
        data: dict[str, Any] = json.load(f)

    if address is not None:
        # Remove specific IP
        if address in data:
            del data[address]
            print(f"Removed credentials for {address}")
        else:
            print(f"No credentials found for {address}")
            return False
    else:
        # Remove all credentials
        data.clear()
        print("Removed all credentials")

    with CREDENTIALS_FILE.open("w") as f:
        json.dump(data, f, indent=2)

    return True


async def do_pair(
    loop: asyncio.AbstractEventLoop,
    ip_address: str | None = None,
    debug: bool = False,
) -> tuple[AppleTVConfig, str]:
    """Perform Companion pairing and save credentials.

    Args:
        loop: The asyncio event loop.
        ip_address: The Apple TV IP address. If None, scans the network.
        debug: Whether to enable debug output.

    Returns:
        tuple[AppleTVConfig, str]: The configuration and IP address of the paired device.

    """
    if debug:
        print("[DEBUG] Pairing mode enabled")

    if ip_address is not None:
        if debug:
            print(f"[DEBUG] Scanning for Apple TV at {ip_address}...")
        print(f"Scanning for Apple TV at {ip_address}...")
        atvs = await scan(loop, hosts=[ip_address])
    else:
        print("Scanning for Apple TVs on the local network...")
        atvs = await scan(loop)

    if not atvs:
        print("No Apple TV found on the network")
        sys.exit(1)

    # If multiple devices found, let user choose
    if len(atvs) > 1 and ip_address is None:
        print(f"Found {len(atvs)} Apple TV(s):")
        for i, atv in enumerate(atvs, 1):
            print(f"  {i}. {atv.name} ({atv.address})")

        choice = await asyncio.to_thread(input, f"Select device (1-{len(atvs)}): ")
        try:
            config: AppleTVConfig = atvs[int(choice) - 1]
        except (ValueError, IndexError):
            print("Invalid selection")
            sys.exit(1)
    else:
        config: AppleTVConfig = atvs[0]

    ip_address = str(config.address)
    print(f"Pairing with {config.name} at {ip_address}...")

    if debug:
        print(f"[DEBUG] Device info: name={config.name}, address={ip_address}")
        print("[DEBUG] Available services:")
        for service in config.services:
            print(
                f"[DEBUG]   - {service.protocol.name}: pairing={service.pairing.name}, enabled={service.enabled}",
            )

    companion_service: Any = None
    for service in config.services:
        if service.protocol == Protocol.Companion:
            companion_service = service
            break

    if companion_service is None:
        print("Companion service not available for pairing")
        sys.exit(1)

    if companion_service.pairing == PairingRequirement.NotNeeded:
        print("Pairing not required for Companion")
        return config, ip_address

    print(f"Pairing required: {companion_service.pairing.name}")

    pairing = await pair(config, Protocol.Companion, loop)
    await pairing.begin()

    if pairing.device_provides_pin:
        pin = await asyncio.to_thread(input, "Enter the PIN shown on Apple TV: ")
        pairing.pin(pin)
    else:
        pin_code = "1234"
        pairing.pin(pin_code)
        print(f"Enter this PIN on your Apple TV: {pin_code}")
        await asyncio.to_thread(input, "Press Enter once you've entered the PIN...")

    await pairing.finish()

    if not pairing.has_paired:
        print("Pairing failed")
        sys.exit(1)

    print("Pairing successful!")

    # Save credentials
    credentials: str = pairing.service.credentials
    await save_credentials(ip_address, Protocol.Companion, credentials)
    print(f"Credentials saved to {CREDENTIALS_FILE}")

    return config, ip_address


async def do_unpair(ip_address: str | None = None, debug: bool = False) -> None:
    """Remove pairing credentials.

    Args:
        ip_address: The IP address to remove. If None, removes all credentials.
        debug: Whether to enable debug output.

    """
    stored_ips: list[str] = get_stored_ips()

    if debug:
        print(f"[DEBUG] Stored IPs: {stored_ips}")

    if not stored_ips:
        print("No stored credentials found.")
        return

    if ip_address is not None:
        # Remove specific IP
        if ip_address in stored_ips:
            confirm = await asyncio.to_thread(
                input, f"Remove credentials for {ip_address}? [y/N]: ",
            )
            if confirm.lower() in ("y", "yes"):
                remove_credentials(ip_address)
        else:
            print(f"No credentials found for {ip_address}")
    # Remove all credentials
    elif len(stored_ips) == 1:
        confirm = await asyncio.to_thread(
            input, f"Remove credentials for {stored_ips[0]}? [y/N]: ",
        )
        if confirm.lower() in ("y", "yes"):
            remove_credentials(stored_ips[0])
    else:
        print(f"Stored credentials for: {', '.join(stored_ips)}")
        confirm = await asyncio.to_thread(input, "Remove ALL credentials? [y/N]: ")
        if confirm.lower() in ("y", "yes"):
            remove_credentials()


async def load_sequence(filepath: Path) -> dict[str, Any]:
    """Load a sequence from a JSON file.

    Args:
        filepath: Path to the JSON sequence file.

    Returns:
        dict[str, Any]: The sequence dictionary with 'name' and 'steps' keys.

    Raises:
        SystemExit: If the file is not found or invalid.

    """
    exists: bool = await asyncio.to_thread(filepath.exists)
    if not exists:
        print(f"Sequence file not found: {filepath}")
        sys.exit(1)

    content: str = await asyncio.to_thread(filepath.read_text)
    sequence: dict[str, Any] = json.loads(content)

    # Basic validation
    if "steps" not in sequence:
        print(f"Invalid sequence file: {filepath}")
        sys.exit(1)

    return sequence


async def run_sequence(
    loop: asyncio.AbstractEventLoop,
    config: AppleTVConfig,
    sequence: dict[str, Any],
    ip_address: str,
    delay_factor: float = 1.5,
    debug: bool = False,
) -> None:
    """Execute a command sequence.

    Args:
        loop: The asyncio event loop.
        config: The Apple TV configuration.
        sequence: The sequence dictionary with steps to execute.
        ip_address: The IP address of the Apple TV.
        delay_factor: Factor to multiply all delays by (default: 1.5).
        debug: Whether to enable debug output.

    Raises:
        SystemExit: If connection fails or sequence cannot be executed.

    """
    atv: Any = None
    try:
        # Load Companion credentials if available
        companion_service: Any = None
        for service in config.services:
            if service.protocol == Protocol.Companion:
                companion_service = service
                creds: str | None = await load_credentials(
                    ip_address, Protocol.Companion,
                )
                if creds is not None:
                    service.credentials = creds
                    if debug:
                        print("[DEBUG] Companion credentials loaded")
                    print("Companion credentials loaded")

        if companion_service is None:
            print("Companion service not available")
            sys.exit(1)

        if debug:
            print("[DEBUG] Disabling non-Companion services")

        # Disable other services
        for service in config.services:
            service.enabled = service.protocol == Protocol.Companion

        # Connect
        atv = await connect(config, loop)
        print(f"Connected (delay factor: {delay_factor}x)")

        if debug:
            print(f"[DEBUG] Connected to: {config.name} ({ip_address})")

        # Execute each step in the sequence
        sequence_name: str = sequence.get("name", "Sequence")
        print(f"Executing '{sequence_name}'...")

        for i, step in enumerate(sequence["steps"], 1):
            action: str = step["action"]
            delay: float = step.get("delay", 0)
            actual_delay: float = delay * delay_factor

            # Execute action
            remote = atv.remote_control
            if not hasattr(remote, action):
                print(f"Action '{action}' not supported")
                continue

            if debug:
                print(
                    f"[DEBUG] Step {i}: action={action}, delay={delay}s, actual_delay={actual_delay:.2f}s",
                )

            func = getattr(remote, action)
            await func()
            print(f"  {i}. {action}")

            # Wait for delay (with factor)
            await asyncio.sleep(actual_delay)

    except Exception as e:
        print(f"Error: {e}")

        traceback.print_exc()
        sys.exit(1)
    finally:
        if atv is not None:
            await asyncio.gather(*atv.close())


async def _main() -> None:
    """Main async entry point.

    Parses command line arguments and executes the appropriate action
    (pair, unpair, or run sequence).
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Execute command sequences on Apple TV via pyatv",
    )
    parser.add_argument(
        "-s",
        "--sequence",
        type=Path,
        default=DEFAULT_SEQUENCE_FILE,
        help="JSON file containing the sequence to execute (default: default.json)",
    )
    parser.add_argument(
        "--pair",
        action="store_true",
        help="Pair with Apple TV and save credentials",
    )
    parser.add_argument(
        "--unpair",
        action="store_true",
        help="Remove pairing credentials",
    )
    parser.add_argument(
        "--ip",
        help="Apple TV IP address (overrides stored credentials)",
    )
    parser.add_argument(
        "-d",
        "--delay-factor",
        type=float,
        default=1.5,
        help="Multiply all delays by this factor (default: 1.5)",
    )
    parser.add_argument(
        "-v",
        "--debug",
        action="store_true",
        help="Enable debug output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    args: argparse.Namespace = parser.parse_args()

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    if args.pair:
        # For pairing: --ip is optional, will scan network if not provided
        config, ip_address = await do_pair(loop, args.ip, args.debug)
    elif args.unpair:
        await do_unpair(args.ip, args.debug)
    else:
        # Determine IP address: --ip argument > stored credentials
        ip_address: str | None = args.ip
        if ip_address is None:
            ip_address = get_stored_ip()

        if ip_address is None:
            stored_ips: list[str] = get_stored_ips()
            if stored_ips:
                print(
                    f"No IP specified. Found stored credentials for: {', '.join(stored_ips)}",
                )
                print(
                    "Use --ip to specify which one, or run --pair to pair with a new device.",
                )
            else:
                print("No IP address specified and no stored credentials found.")
                print("Use --ip to specify an IP address, or run --pair first.")
            sys.exit(1)

        # Scan for the Apple TV
        print(f"Scanning for Apple TV at {ip_address}...")
        atvs = await scan(loop, hosts=[ip_address])
        if not atvs:
            print(f"No device found at {ip_address}")
            print("Try running --pair to scan for devices on the network.")
            sys.exit(1)

        config: AppleTVConfig = atvs[0]
        print(f"Found: {config.name}")
        for service in config.services:
            print(
                f"  {service.protocol.name}: enabled={service.enabled}, pairing={service.pairing.name}",
            )

        # Load sequence
        sequence: dict[str, Any] = await load_sequence(args.sequence)
        print(f"Sequence loaded: {sequence.get('name', 'Unknown')}")
        await run_sequence(
            loop, config, sequence, ip_address, args.delay_factor, args.debug,
        )


def main() -> None:
    """Entry point for pipx.

    Runs the async main function using asyncio.run.
    """
    asyncio.run(_main())


if __name__ == "__main__":
    main()
