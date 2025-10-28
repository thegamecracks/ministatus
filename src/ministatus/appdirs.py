import os
import platformdirs

_appname = "ministatus"
if _appsuffix := os.getenv("MIST_APPDIR_SUFFIX"):
    _appname = f"{_appname}-{_appsuffix}"

APP_DIRS = platformdirs.PlatformDirs(
    appauthor="thegamecracks",
    appname=_appname,
    ensure_exists=True,
    opinion=True,
)
DB_PATH = APP_DIRS.user_data_path / f"{APP_DIRS.appname}.db"
