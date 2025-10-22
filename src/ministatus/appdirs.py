import platformdirs

APP_DIRS = platformdirs.PlatformDirs(
    appauthor="thegamecracks",
    appname="ministatus",
    ensure_exists=True,
    opinion=True,
)
DB_PATH = APP_DIRS.user_data_path / f"{APP_DIRS.appname}.db"
