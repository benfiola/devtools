from devtools.data import data_folder

__version__ = data_folder.joinpath("version.txt").read_text().strip()
