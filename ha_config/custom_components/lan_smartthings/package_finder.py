import logging
import os
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec, SourceFileLoader
import importlib
from typing import List

_LOGGER = logging.getLogger(__name__)

MY_PACKAGE_NAME = __package__
PROXY_PACKAGE_NAME = MY_PACKAGE_NAME + "." + "smartthings"
SOURCE_PACKAGE_NAME = "homeassistant.components.smartthings"

MY_DIR_ROOT = os.path.dirname(__file__)[:-len(MY_PACKAGE_NAME)]
source = importlib.import_module(SOURCE_PACKAGE_NAME)
SOURCE_DIR = os.path.dirname(source.__file__)[:-len(SOURCE_PACKAGE_NAME)]

PATH_TREE: List[str] = []


class RedirectPackageFinder(MetaPathFinder):
    @staticmethod
    def get_spec(package_name: str) -> ModuleSpec:
        if package_name.startswith(PROXY_PACKAGE_NAME):  # first check proxy
            source_path = WrappedLoader.sourcepath(package_name)
            if not os.path.exists(source_path):
                return None
            filepath = os.path.join(MY_DIR_ROOT, *package_name.split("."))
            loader = WrappedLoader(package_name, None)
            spec = ModuleSpec(package_name,
                              origin=filepath,
                              loader=loader,
                              is_package=package_name == PROXY_PACKAGE_NAME)
            spec.has_location = True
            return spec
        if package_name.startswith(MY_PACKAGE_NAME):
            source_path = WrappedLoader.sourcepath(package_name)
            if not os.path.exists(source_path):
                return None
            filepath = os.path.join(MY_DIR_ROOT, *package_name.split("."))
            loader = WrappedLoader(package_name, None)
            spec = ModuleSpec(package_name,
                              origin=filepath,
                              loader=loader,
                              is_package=package_name == MY_PACKAGE_NAME)
            spec.has_location = True
            return spec
        return None

    def find_spec(self, fullname: str, path, target=None):

        if fullname.startswith(PROXY_PACKAGE_NAME):
            if PATH_TREE and PATH_TREE[-1].startswith(PROXY_PACKAGE_NAME):
                # called from proxy so redirect to our package
                fullname = MY_PACKAGE_NAME + fullname[len(PROXY_PACKAGE_NAME):]
                return self.get_spec(fullname)
        if fullname.startswith(MY_PACKAGE_NAME):
            return self.get_spec(fullname)
        return None


class WrappedLoader(SourceFileLoader):

    @staticmethod
    def sourcepath(name):
        if name.startswith(PROXY_PACKAGE_NAME):
            redirect_name = SOURCE_PACKAGE_NAME + \
                name[len(PROXY_PACKAGE_NAME):]
            if name == PROXY_PACKAGE_NAME:
                return os.path.join(SOURCE_DIR, *redirect_name.split("."), "__init__.py")
            else:
                return os.path.join(SOURCE_DIR, *redirect_name.split(".")) + ".py"
        if name.startswith(MY_PACKAGE_NAME):
            if name == MY_PACKAGE_NAME:
                return os.path.join(MY_DIR_ROOT, *name.split("."), "__init__.py")
            else:
                return os.path.join(MY_DIR_ROOT, *name.split(".")) + ".py"
        raise ValueError()

    def get_filename(self, name):
        return self.sourcepath(name)

    def exec_module(self, module) -> None:
        PATH_TREE.append(module.__name__)
        _LOGGER.debug(f"Entering module {module.__name__}")
        super().exec_module(module)
        name = PATH_TREE.pop()
        _LOGGER.debug(f"Exiting module {name}")
