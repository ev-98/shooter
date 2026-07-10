"""Single source of truth for the app's identity and version.

Read by the UI (title-screen version label) and by build tooling
(PyInstaller spec, CI workflow) for artifact naming and platform metadata.
Bump VERSION here before cutting a release.
"""
APP_NAME = "shooter"
VERSION  = "1.0.1"
