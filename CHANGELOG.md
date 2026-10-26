# Changelog

What changed in each release. The section for a version becomes the notes of that release on GitHub.

## 0.1.0

The first release.

- One page for a home server's monitor: containers, network, power, hardware, GPU and an event log, refreshed every second.
- A centrepiece showing the server with a line to every container and network peer it talks to.
- Colour only for trouble: anything unhealthy turns amber or red everywhere it is shown at once.
- Runs on Linux, Windows and macOS. Linux reads the most; the readme lists what the other two leave empty.
- A one-line install that puts everything in one folder, starts the dashboard by itself, and removes it all again with one uninstall script.
- Settings in one file, including `DASH_FPS` for the frame rate of the moving parts (30 by default).
