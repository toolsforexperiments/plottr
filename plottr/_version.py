def _get_version() -> str:
    from pathlib import Path

    import versioningit

    import plottr

    path = Path(plottr.__file__).parent
    return versioningit.get_version(project_dir=path.parent)


__version__ = _get_version()
