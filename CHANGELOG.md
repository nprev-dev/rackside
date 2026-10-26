# Changelog

What changed in each release. The section for a version becomes the notes of that release on GitHub.

## 0.2.0

Rack Dashboard is now called Rackside.

- The command is `rackside`, the install folder `~/rackside` (`rackside` in your user folder on Windows), and the GitHub repository `nprev-dev/rackside`. Old links to the repository still work.
- Installing 0.2.0 over 0.1.0 takes the old install over: its start-up entry is replaced, and its folder moves to the new name with your settings and history in it. An install you had put in a folder of your own stays in that folder.
- The page title and every message say Rackside.

## 0.1.0

The first release.

- One page for a home server's monitor: containers, network, power, hardware, GPU and an event log, refreshed every second.
- A centrepiece showing the server with a line to every container and network peer it talks to.
- Colour only for trouble: anything unhealthy turns amber or red everywhere it is shown at once.
- Runs on Linux, Windows and macOS. Linux reads the most; the readme lists what the other two leave empty.
- A one-line install that puts everything in one folder, starts the dashboard by itself, and removes it all again with one uninstall script.
- Settings in one file, including `DASH_FPS` for the frame rate of the moving parts (30 by default).
