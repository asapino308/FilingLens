"""Finder layout for a read-only drag-to-Applications disk image."""
application = defines["app"]
format = "UDZO"
filesystem = "HFS+"
files = [application, (defines["instructions"], "Install FilingLens.txt")]
symlinks = {"Applications": "/Applications"}
background = "#f5f4ef"
window_rect = ((180, 120), (660, 400))
icon_locations = {"FilingLens.app": (170, 140), "Applications": (490, 140), "Install FilingLens.txt": (330, 285)}
icon_size = 100
text_size = 14
hide_extensions = []  # Preserve the signed app bundle without FinderInfo attributes.
default_view = "icon-view"
show_status_bar = False
show_toolbar = False
show_sidebar = False
