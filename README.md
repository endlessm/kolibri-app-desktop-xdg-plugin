# Kolibri Linux desktop app integration plugin

This is a Kolibri plugin which generates Linux desktop launchers and icons for Kolibri channels. These files are created automatically in `$KOLIBRI_HOME/content/xdg/share`. This plugin is intended to be used inside a Kolibri desktop application such as <https://flathub.org/apps/details/org.learningequality.Kolibri>.

## Usage

Install the plugin from pypi:

```
pip install kolibri-app-desktop-xdg-plugin
```

Enable the plugin in Kolibri and generate launchers:

```
kolibri plugin enable kolibri_app_desktop_xdg_plugin
kolibri manage app_desktop_xdg_update_launchers
```

Additional desktop launchers will be generated automatically when channels are added or removed. For these launchers to appear on your desktop, you will need to add their location to the `XDG_DATA_DIRS` environment variable. To do this in most Linux distributions, create a file named `/usr/lib/systemd/user-environment-generators/61-kolibri-app-desktop-xdg-plugin` with the following contents, then log out and log in again:

```
#!/bin/bash
XDG_DATA_DIRS="$HOME/.kolibri/content/xdg/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
echo "XDG_DATA_DIRS=$XDG_DATA_DIRS"
```

You can substitute the path to Kolibri's home directory for `${HOME}/.kolibri`.

